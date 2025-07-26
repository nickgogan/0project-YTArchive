#!/bin/bash
# YTArchive Test Suite Audit Runner
# Simple script to run test audits with common configurations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🔍 YTArchive Test Suite Audit Runner"
echo "===================================="
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Function to run audit with different formats
run_audit() {
    local format="$1"
    local output_file="$2"

    echo "📊 Running audit in $format format..."

    if [ -n "$output_file" ]; then
        python scripts/test_audit.py --$format --output "$output_file"
        echo "✅ Report saved to: $output_file"
    else
        python scripts/test_audit.py --$format
    fi
    echo ""
}

# Parse command line arguments
case "${1:-console}" in
    "console"|"")
        echo "📺 Console Report:"
        python scripts/test_audit.py
        ;;
    "json")
        run_audit "json" "${2:-reports/test_audit.json}"
        ;;
    "markdown")
        run_audit "markdown" "${2:-reports/test_audit.md}"
        ;;
    "all")
        echo "📊 Generating all report formats..."
        mkdir -p reports

        echo "📺 Console Report:"
        python scripts/test_audit.py
        echo ""

        echo "📄 JSON Report:"
        run_audit "json" "reports/test_audit.json"

        echo "📝 Markdown Report:"
        run_audit "markdown" "reports/test_audit.md"

        echo "🎉 All reports generated successfully!"
        ;;
    "strict")
        echo "🔒 Running strict validation..."
        python scripts/test_audit.py --strict
        ;;
    "help")
        echo "Usage: $0 [console|json|markdown|all|strict|help] [output_file]"
        echo ""
        echo "Commands:"
        echo "  console   - Display console report (default)"
        echo "  json      - Generate JSON report"
        echo "  markdown  - Generate Markdown report"
        echo "  all       - Generate all report formats"
        echo "  strict    - Run with strict validation (fails on issues)"
        echo "  help      - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                              # Console report"
        echo "  $0 json                         # JSON to reports/test_audit.json"
        echo "  $0 json my_report.json          # JSON to custom file"
        echo "  $0 all                          # All formats"
        echo "  $0 strict                       # Strict validation"
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo "Run '$0 help' for usage information."
        exit 1
        ;;
esac
