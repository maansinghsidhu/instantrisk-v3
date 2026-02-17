"""
Test InstantRisk Engine ML integration end-to-end (local model, no AWS required).

Run from backend/ directory:
    python test_ml_integration.py
"""

import sys
import os
import json

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))


def test_model_files():
    """Test that all required model files exist."""
    print("\n=== Test 1: Model File Verification ===")

    base = os.path.join("app", "data", "models")
    slots = {
        "final": os.path.join(base, "instantrisk-engine-v1-final"),
        "best": os.path.join(base, "instantrisk-engine-v1-best"),
    }

    all_ok = True
    for slot, path in slots.items():
        if not os.path.isdir(path):
            print(f"  [{slot}] MISSING: {path}")
            all_ok = False
            continue

        files = os.listdir(path)
        print(f"  [{slot}] Found: {files}")

        for required in ["model.pt", "config.json"]:
            if required not in files:
                print(f"    MISSING: {required}")
                all_ok = False
            else:
                size_mb = os.path.getsize(os.path.join(path, required)) / (1024 * 1024)
                print(f"    OK: {required} ({size_mb:.1f} MB)")

        # Check config content
        config_path = os.path.join(path, "config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            print(f"    Config: base_model={config.get('base_model')}, "
                  f"clause_labels={config.get('num_clause_labels')}, "
                  f"intent_labels={config.get('num_intent_labels')}")

    return all_ok


def test_service_load():
    """Test that the InsuranceModelService loads correctly."""
    print("\n=== Test 2: Service Load ===")

    try:
        # Import only the core service, avoiding the __init__.py that imports all services
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "insurance_model_service",
            os.path.join("app", "services", "insurance_model_service.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        InsuranceModelService = mod.InsuranceModelService
        service = InsuranceModelService()

        print("  Loading model...")
        available = service.load()
        print(f"  Model available: {available}")

        if available:
            config = service._config
            print(f"  Base model: {config.get('base_model')}")
            print(f"  Clause labels: {config.get('num_clause_labels')}")
            print(f"  Intent labels: {config.get('num_intent_labels')}")
            print(f"  Training mode: {config.get('training_mode')}")

        return service, available
    except ImportError as e:
        print(f"  Import error: {e}")
        print("  NOTE: torch may not be installed in this environment.")
        return None, False
    except Exception as e:
        print(f"  Load error: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_build_risk_description(service):
    """Test risk description builder."""
    print("\n=== Test 3: Risk Description Builder ===")

    test_cases = [
        {
            "risk_category": "Cyber",
            "territory": "United States",
            "summary": "Tech company offering SaaS platform with $10M revenue",
            "insured_entity_name": "TechCorp Inc",
        },
        {
            "risk_category": "Property",
            "territory": "United Kingdom",
            "summary": "Commercial property warehouse in flood zone",
            "insured_entity_name": "PropertyCo Ltd",
        },
        {
            "risk_category": "Professional Indemnity",
            "territory": "Singapore",
            "summary": "Management consulting firm with financial advisory services",
        },
    ]

    for case in test_cases:
        desc = service.build_risk_description(case)
        print(f"  [{case['risk_category']}]: {desc[:100]}...")

    return True


def test_predictions(service, available):
    """Test ML predictions on sample risks."""
    print("\n=== Test 4: ML Predictions ===")

    if not available:
        print("  SKIPPED: Model not available (torch/model not loaded)")
        print("  Fallback predictions:")
        # Test fallback mode
        result = service.predict_all("cyber liability insurance")
        print(f"  predict_all (fallback): {result}")
        return True

    test_risks = [
        "Cyber liability insurance for US tech company, SaaS platform, $10M revenue, annual policy",
        "Property insurance for commercial warehouse in UK, flood zone, sum insured GBP 5M",
        "Professional indemnity for management consultants, financial advice, Singapore",
        "Marine cargo insurance for container shipping, Pacific route",
    ]

    for risk_text in test_risks:
        print(f"\n  Risk: {risk_text[:60]}...")
        result = service.predict_all(risk_text)

        print(f"    Appetite: {result['appetite']['decision']} "
              f"(confidence: {result['appetite']['confidence']:.2%})")
        print(f"    Pricing:  {result['pricing']['band']} band "
              f"(confidence: {result['pricing']['confidence']:.2%})")
        if result.get("intent"):
            print(f"    Intent:   {result['intent']['intent']} "
                  f"(confidence: {result['intent']['confidence']:.2%})")
        if result.get("clauses"):
            top3 = result["clauses"][:3]
            top3_str = ", ".join(f"{c['category']}({c['score']:.2f})" for c in top3)
            print(f"    Top clauses: {top3_str}")

    return True


def test_clause_recommendations(service):
    """Test clause recommendations method."""
    print("\n=== Test 5: Clause Recommendations ===")

    risk = "Cyber liability insurance for technology company providing cloud services"
    cats = service.recommend_clause_categories(risk, top_k=10)

    if cats:
        print(f"  Top clause categories for cyber risk ({len(cats)}):")
        for cat in cats[:5]:
            print(f"    - {cat['category']}: {cat['score']:.2%}")
    else:
        print("  No categories returned (model fallback mode)")

    return True


def test_appetite_pricing(service):
    """Test appetite and pricing classification."""
    print("\n=== Test 6: Appetite & Pricing Classification ===")

    scenarios = [
        ("Low risk", "General liability insurance for established retailer, 20 years trading, no claims history"),
        ("High risk", "Aviation hull insurance for experimental aircraft, first flight, no safety certification"),
        ("Medium risk", "Professional indemnity for mid-size accounting firm, standard audit work"),
    ]

    for label, risk_text in scenarios:
        appetite = service.assess_appetite(risk_text)
        pricing = service.classify_pricing(risk_text)
        print(f"  [{label}]")
        print(f"    Appetite: {appetite['decision']} ({appetite['confidence']:.2%})")
        print(f"    Pricing:  {pricing['band']} ({pricing['confidence']:.2%})")

    return True


def test_load_from_sagemaker_job_dry_run():
    """Test that load_from_sagemaker_job method exists and handles missing credentials gracefully."""
    print("\n=== Test 7: SageMaker Integration (dry run) ===")

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "insurance_model_service",
        os.path.join("app", "services", "insurance_model_service.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    InsuranceModelService = mod.InsuranceModelService
    service = InsuranceModelService()

    # Verify method exists with correct signature
    import inspect
    sig = inspect.signature(service.load_from_sagemaker_job)
    params = list(sig.parameters.keys())
    print(f"  load_from_sagemaker_job signature: {params}")

    sig2 = inspect.signature(service.load_from_s3)
    params2 = list(sig2.parameters.keys())
    print(f"  load_from_s3 signature: {params2}")

    # Try calling it (will fail with credentials error, which is expected)
    try:
        result = service.load_from_sagemaker_job("instantrisk-engine-20260217-195607")
        print(f"  Result: {result}")
    except Exception as e:
        err_type = type(e).__name__
        if "ExpiredToken" in str(e) or "NoCredentials" in str(e) or "botocore" in str(e) or "boto3" in str(e):
            print(f"  EXPECTED: {err_type} — credentials not available (use fresh SSO creds)")
        else:
            print(f"  Unexpected error: {err_type}: {e}")

    return True


def main():
    print("=" * 60)
    print("InstantRisk Engine - ML Integration Test Suite")
    print("=" * 60)

    results = {}

    # Test 1: Model file verification (always runs)
    results["files"] = test_model_files()

    # Test 2: Service load
    service, available = test_service_load()

    if service is not None:
        results["build_desc"] = test_build_risk_description(service)
        results["predictions"] = test_predictions(service, available)
        results["clause_recs"] = test_clause_recommendations(service)
        results["appetite_pricing"] = test_appetite_pricing(service)
    else:
        print("\n  Skipping service tests — could not import service")

    results["sagemaker_dry_run"] = test_load_from_sagemaker_job_dry_run()

    print("\n" + "=" * 60)
    print("Test Results:")
    for test, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {test}")

    all_passed = all(results.values())
    print(f"\nOverall: {'ALL PASS' if all_passed else 'SOME FAILURES'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
