#!/bin/bash

# Saga Graph Complete Setup Script
# Automates the setup steps described in setup.md
set -e

VENV_NAME=".venv"
PYTHON_CMD="python3"
REQUIRED_PYTHON_VERSION="3.12"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

check_python_version() {
    print_step "Checking Python version..."
    
    if ! command -v $PYTHON_CMD &> /dev/null; then
        print_error "$PYTHON_CMD is not installed or not in PATH"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    PYTHON_MAJOR_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f1-2)
    
    if [[ "$PYTHON_MAJOR_MINOR" < "$REQUIRED_PYTHON_VERSION" ]]; then
        print_error "Python $REQUIRED_PYTHON_VERSION or higher is required. Found: $PYTHON_VERSION"
        exit 1
    fi
    
    print_success "Python $PYTHON_VERSION found"
}

setup_python_env() {
    print_step "Setting up Python virtual environment..."
    
    # Create virtual environment
    if [ -d "$VENV_NAME" ]; then
        print_warning "Virtual environment already exists at $VENV_NAME"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf $VENV_NAME
        else
            print_step "Using existing virtual environment"
        fi
    fi
    
    if [ ! -d "$VENV_NAME" ]; then
        echo "Creating virtual environment: $VENV_NAME"
        $PYTHON_CMD -m venv $VENV_NAME
    fi
    
    # Activate virtual environment
    echo "Activating virtual environment..."
    source $VENV_NAME/bin/activate
    
    # Upgrade pip and install build tools
    echo "Upgrading pip and installing build tools..."
    python -m pip install -U pip wheel setuptools
    
    # Install dependencies from pyproject.toml
    if [ -f "pyproject.toml" ]; then
        echo "Installing dependencies from pyproject.toml..."
        pip install -e .
        print_success "Dependencies installed successfully!"
    else
        print_error "pyproject.toml not found - cannot install dependencies"
        exit 1
    fi
}

check_environment_variables() {
    print_step "Checking required environment variables..."
    
    MISSING_VARS=()
    
    # Check Neo4j variables
    [ -z "$NEO4J_URI" ] && MISSING_VARS+=("NEO4J_URI")
    [ -z "$NEO4J_USER" ] && MISSING_VARS+=("NEO4J_USER") 
    [ -z "$NEO4J_PASSWORD" ] && MISSING_VARS+=("NEO4J_PASSWORD")
    [ -z "$NEO4J_DATABASE" ] && MISSING_VARS+=("NEO4J_DATABASE")
    
    # Check for at least one LLM provider
    if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
        MISSING_VARS+=("OPENAI_API_KEY or ANTHROPIC_API_KEY")
    fi
    
    # News API is optional but warn if missing
    if [ -z "$NEWS_API_KEY" ]; then
        print_warning "NEWS_API_KEY not set - news ingestion will not work"
    fi
    
    if [ ${#MISSING_VARS[@]} -ne 0 ]; then
        print_error "Missing required environment variables:"
        for var in "${MISSING_VARS[@]}"; do
            echo "  - $var"
        done
        echo ""
        echo "Please set these variables in your shell profile (e.g., ~/.zshrc) or export them:"
        echo "  export NEO4J_URI=neo4j://127.0.0.1:7687"
        echo "  export NEO4J_USER=neo4j"
        echo "  export NEO4J_PASSWORD=your_password"
        echo "  export NEO4J_DATABASE=argosgraph"
        echo "  export OPENAI_API_KEY=sk-..."
        echo "  export NEWS_API_KEY=your_perigon_api_key"
        echo ""
        echo "Then restart this script."
        exit 1
    fi
    
    print_success "All required environment variables are set"
}

test_neo4j_connection() {
    print_step "Testing Neo4j connection..."
    
    # Activate venv for the test
    source $VENV_NAME/bin/activate
    
    if python -c "
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.abspath('$0'))
while not os.path.exists(os.path.join(PROJECT_ROOT, 'main.py')) and PROJECT_ROOT != '/':
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.graph.neo4j_client import run_cypher
    result = run_cypher('RETURN 1 AS ok')
    print('Neo4j connection successful')
    exit(0)
except Exception as e:
    print(f'Neo4j connection failed: {e}')
    exit(1)
" 2>/dev/null; then
        print_success "Neo4j connection successful"
    else
        print_error "Neo4j connection failed"
        echo "Please ensure:"
        echo "  1. Neo4j server is running"
        echo "  2. NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD are correct"
        echo "  3. Database $NEO4J_DATABASE exists or user has admin rights to create it"
        exit 1
    fi
}

test_llm_connection() {
    print_step "Testing LLM connection..."
    
    # Activate venv for the test
    source $VENV_NAME/bin/activate
    
    if python -c "
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.abspath('$0'))
while not os.path.exists(os.path.join(PROJECT_ROOT, 'main.py')) and PROJECT_ROOT != '/':
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.llm.llm_router import get_llm
    from src.llm.config import ModelTier
    llm = get_llm(ModelTier.SIMPLE)
    response = llm.invoke('ping')
    print('LLM connection successful')
    exit(0)
except Exception as e:
    print(f'LLM connection failed: {e}')
    exit(1)
" 2>/dev/null; then
        print_success "LLM connection successful"
    else
        print_error "LLM connection failed"
        echo "Please check your LLM provider API keys and configuration"
        exit 1
    fi
}

seed_anchor_nodes() {
    print_step "Seeding anchor nodes..."
    
    # Activate venv for seeding
    source $VENV_NAME/bin/activate
    
    if [ -f "user_anchor_nodes.py" ]; then
        if python user_anchor_nodes.py; then
            print_success "Anchor nodes seeded successfully"
        else
            print_warning "Failed to seed anchor nodes - you may need to do this manually"
        fi
    else
        print_warning "user_anchor_nodes.py not found - skipping anchor node seeding"
    fi
}

test_news_api() {
    print_step "Testing News API connection..."
    
    if [ -z "$NEWS_API_KEY" ]; then
        print_warning "NEWS_API_KEY not set - skipping news API test"
        return
    fi
    
    # Activate venv for the test
    source $VENV_NAME/bin/activate
    
    if python -m perigon.news_api_client 2>/dev/null; then
        print_success "News API connection successful"
    else
        print_warning "News API test failed - check your NEWS_API_KEY"
    fi
}

run_type_checks() {
    print_step "Running type checks with MyPy..."
    
    # Activate venv for type checking
    source $VENV_NAME/bin/activate
    
    # Check if MyPy is available
    if ! python -c "import mypy" 2>/dev/null; then
        print_warning "MyPy not found - installing development dependencies"
        pip install -e ".[dev]"
    fi
    
    # Run type checking on core modules
    if python scripts/typecheck.py 2>/dev/null; then
        print_success "Type checking passed"
    else
        print_warning "Type checking found issues - review output above"
        print_warning "You can run 'python scripts/typecheck.py' later to see detailed results"
    fi
}

main() {
    echo "🚀 Saga Graph Setup Script"
    echo "This script automates the setup steps described in setup.md"
    echo ""
    
    check_python_version
    setup_python_env
    check_environment_variables
    test_neo4j_connection
    test_llm_connection
    test_news_api
    seed_anchor_nodes
    run_type_checks
    
    echo ""
    print_success "Setup complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Activate the virtual environment:"
    echo "     source $VENV_NAME/bin/activate"
    echo ""
    echo "  2. Test with a sample report:"
    echo "     python Reports/export_asset_analysis_pdf.py"
    echo ""
    echo "  3. Run type checking (recommended for development):"
    echo "     python scripts/typecheck.py"
    echo ""
    echo "  4. Or run the main loop:"
    echo "     python main.py"
    echo ""
    echo "  Development tools:"
    echo "     pre-commit install    # Enable pre-commit hooks"
    echo "     deactivate           # Exit virtual environment"
    echo ""
    echo "📖 See setup.md for detailed information about configuration options."
}

# Run main function
main