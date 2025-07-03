#!/bin/bash
# Quick install script for ML dependencies

echo "Installing ML dependencies for Memory Service..."

# Activate virtual environment if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Install PyTorch for Apple Silicon
pip install --upgrade pip
pip install torch torchvision torchaudio

# Install sentence-transformers and transformers
pip install sentence-transformers transformers

# Install pgvector support
pip install pgvector

echo "✅ ML dependencies installed!"
echo "Note: First run will download e5-large model (~1.3GB)"
