#!/bin/bash
# Make all test scripts executable

chmod +x test_plugins_quick.sh
chmod +x test_plugin_docker.sh
chmod +x titan-plugins.py

echo "✅ Scripts are now executable"
echo ""
echo "You can now run:"
echo "  ./test_plugins_quick.sh    - Quick local test"
echo "  ./test_plugin_docker.sh    - Full Docker test"
echo "  python test_plugin_integration.py - Integration tests"
