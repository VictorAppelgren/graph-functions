#!/bin/bash

# Run with source set_env_vars.sh

# Neo4j Configuration
export NEO4J_URI="neo4j://127.0.0.1:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password"
export NEO4J_DATABASE="argosgraph"

# API Keys
export OPENAI_API_KEY="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"
export ANTHROPIC_API_KEY="sk-ant-your_anthropic_key_here"
export NEWS_API_KEY="42d445d4-0839-450f-a747-901e63b89bb2"

echo "Environment variables set successfully!"
echo "You can now run your setup script."