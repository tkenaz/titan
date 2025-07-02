#!/bin/bash
# Quick script to run memory service tests

cd /Users/mvyshhnyvetska/Desktop/titan

# Ensure we have the env vars
source .env

# Run the test
python3 test_memory_fixes.py
