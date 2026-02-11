#!/bin/bash
# InstantRisk V2 - Mac Setup Script
# Run this ONCE on your Mac to set up the development environment

set -e

echo "=========================================="
echo "  InstantRisk V2 - Mac Setup"
echo "=========================================="
echo ""

# Check macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script must be run on macOS"
    exit 1
fi

# Install Homebrew if not present
if ! command -v brew &> /dev/null; then
    echo "📦 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
echo "✅ Homebrew installed"

# Install Flutter
if ! command -v flutter &> /dev/null; then
    echo "📦 Installing Flutter..."
    brew install flutter
fi
echo "✅ Flutter installed: $(flutter --version | head -1)"

# Install CocoaPods
if ! command -v pod &> /dev/null; then
    echo "📦 Installing CocoaPods..."
    sudo gem install cocoapods
fi
echo "✅ CocoaPods installed: $(pod --version)"

# Install fastlane
if ! command -v fastlane &> /dev/null; then
    echo "📦 Installing Fastlane..."
    brew install fastlane
fi
echo "✅ Fastlane installed: $(fastlane --version | head -1)"

# Check Xcode
if ! command -v xcodebuild &> /dev/null; then
    echo ""
    echo "⚠️  Xcode not found!"
    echo "   Please install Xcode from the App Store:"
    echo "   https://apps.apple.com/app/xcode/id497799835"
    echo ""
    echo "   After installing, run:"
    echo "   sudo xcode-select --switch /Applications/Xcode.app"
    echo "   sudo xcodebuild -license accept"
    exit 1
fi
echo "✅ Xcode installed: $(xcodebuild -version | head -1)"

# Accept Xcode license
sudo xcodebuild -license accept 2>/dev/null || true

# Flutter doctor
echo ""
echo "🩺 Running Flutter Doctor..."
flutter doctor

echo ""
echo "=========================================="
echo "  ✅ Mac Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. cd to project: cd /path/to/instantrisk-v2/mobile"
echo "2. Build iOS: ./scripts/build_ios.sh"
echo "3. Or deploy: fastlane ios deploy_testflight"
echo ""
