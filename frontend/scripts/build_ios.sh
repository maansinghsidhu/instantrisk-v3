#!/bin/bash
# InstantRisk V2 - iOS Build Script
# Run this on your Mac laptop
#
# Prerequisites:
# - Xcode installed (App Store)
# - Flutter installed (brew install flutter)
# - CocoaPods installed (sudo gem install cocoapods)

set -e

echo "=========================================="
echo "  InstantRisk V2 - iOS Build"
echo "=========================================="
echo ""

# Check we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script must be run on macOS"
    exit 1
fi

# Check Xcode
if ! command -v xcodebuild &> /dev/null; then
    echo "❌ Xcode not found. Install from App Store."
    exit 1
fi
echo "✅ Xcode found: $(xcodebuild -version | head -1)"

# Check Flutter
if ! command -v flutter &> /dev/null; then
    echo "❌ Flutter not found. Install with: brew install flutter"
    exit 1
fi
echo "✅ Flutter found: $(flutter --version | head -1)"

# Check CocoaPods
if ! command -v pod &> /dev/null; then
    echo "⚠️  CocoaPods not found. Installing..."
    sudo gem install cocoapods
fi
echo "✅ CocoaPods found: $(pod --version)"

# Navigate to project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo ""
echo "📦 Getting dependencies..."
flutter pub get

echo ""
echo "🍎 Installing iOS pods..."
cd ios
pod install --repo-update
cd ..

echo ""
echo "🔨 Building iOS Release..."
flutter build ios --release --no-codesign

echo ""
echo "=========================================="
echo "  ✅ iOS Build Complete!"
echo "=========================================="
echo ""
echo "Output: build/ios/iphoneos/Runner.app"
echo ""
echo "Next steps:"
echo "1. Open ios/Runner.xcworkspace in Xcode"
echo "2. Select your signing team"
echo "3. Archive: Product > Archive"
echo "4. Distribute to App Store or TestFlight"
echo ""
