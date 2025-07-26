#!/bin/bash

# YTArchive Services Startup Script
# Starts all YTArchive microservices for development or production use

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PYTHON_CMD="python"
SERVICES_DIR="services"
LOG_DIR="logs"
PID_DIR="pids"

# Service configurations
declare -A SERVICES=(
    ["jobs"]="8001"
    ["metadata"]="8002"
    ["download"]="8003"
    ["storage"]="8004"
)

# Logging functions
log() {
    echo -e "${BLUE}[START]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check if Python is available
    if ! command -v $PYTHON_CMD &> /dev/null; then
        error "Python is not available. Please install Python 3.12+"
    fi

    # Check if we're in the correct directory
    if [ ! -f "pyproject.toml" ] || [ ! -d "$SERVICES_DIR" ]; then
        error "Please run this script from the YTArchive root directory"
    fi

    # Check if YouTube API key is set
    if [ -z "$YOUTUBE_API_KEY" ]; then
        warning "YOUTUBE_API_KEY environment variable is not set"
        warning "Services may fail without proper API key configuration"
    fi

    # Create necessary directories
    mkdir -p $LOG_DIR $PID_DIR downloads storage work_plans

    success "Prerequisites check completed"
}

# Check if port is available
check_port() {
    local port=$1
    local service=$2

    if netstat -tuln 2>/dev/null | grep -q ":$port "; then
        warning "Port $port (for $service service) is already in use"
        return 1
    fi
    return 0
}

# Start a single service
start_service() {
    local service=$1
    local port=$2

    log "Starting $service service on port $port..."

    # Check if port is available
    if ! check_port $port $service; then
        error "Cannot start $service service - port $port is in use"
        return 1
    fi

    # Check if service file exists
    local service_file="$SERVICES_DIR/$service/main.py"
    if [ ! -f "$service_file" ]; then
        error "Service file not found: $service_file"
        return 1
    fi

    # Start service in background
    local log_file="$LOG_DIR/${service}_service.log"
    local pid_file="$PID_DIR/${service}_service.pid"

    nohup $PYTHON_CMD $service_file --port $port \
        > $log_file 2>&1 &

    local pid=$!
    echo $pid > $pid_file

    # Wait a moment and check if service started successfully
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        success "$service service started (PID: $pid, Port: $port)"
        return 0
    else
        error "$service service failed to start"
        return 1
    fi
}

# Check service health
check_service_health() {
    local service=$1
    local port=$2

    log "Checking health of $service service..."

    # Wait for service to be ready
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s --max-time 5 "http://localhost:$port/health" >/dev/null 2>&1; then
            success "$service service is healthy"
            return 0
        fi

        echo -n "."
        sleep 1
        ((attempt++))
    done

    echo ""
    warning "$service service health check failed"
    return 1
}

# Start all services
start_all_services() {
    log "Starting YTArchive services..."

    local failed_services=()

    # Start services in dependency order
    for service in jobs metadata download storage; do
        if start_service $service ${SERVICES[$service]}; then
            if check_service_health $service ${SERVICES[$service]}; then
                success "$service service is ready"
            else
                failed_services+=($service)
            fi
        else
            failed_services+=($service)
        fi

        echo ""
    done

    # Report results
    if [ ${#failed_services[@]} -eq 0 ]; then
        success "All services started successfully!"
        return 0
    else
        error "Failed to start services: ${failed_services[*]}"
        return 1
    fi
}

# Display service status
show_status() {
    echo ""
    echo "============================================"
    echo "YTArchive Services Status"
    echo "============================================"

    for service in "${!SERVICES[@]}"; do
        local port=${SERVICES[$service]}
        local pid_file="$PID_DIR/${service}_service.pid"

        echo -n "$service service (port $port): "

        if [ -f "$pid_file" ]; then
            local pid=$(cat $pid_file)
            if kill -0 $pid 2>/dev/null; then
                if curl -s --max-time 2 "http://localhost:$port/health" >/dev/null 2>&1; then
                    echo -e "${GREEN}RUNNING${NC} (PID: $pid)"
                else
                    echo -e "${YELLOW}STARTED${NC} (PID: $pid) - Health check failed"
                fi
            else
                echo -e "${RED}STOPPED${NC} (stale PID file)"
                rm -f $pid_file
            fi
        else
            echo -e "${RED}STOPPED${NC}"
        fi
    done

    echo ""
}

# Display usage information
show_usage_info() {
    echo ""
    echo "============================================"
    echo "YTArchive Usage Information"
    echo "============================================"
    echo ""
    echo "Services are now running and ready for use:"
    echo ""
    echo "🔌 Service Endpoints:"
    for service in "${!SERVICES[@]}"; do
        local port=${SERVICES[$service]}
        echo "   • $service: http://localhost:$port"
    done
    echo ""
    echo "🎯 Quick Start Commands:"
    echo "   • Download video: python cli/main.py download VIDEO_URL"
    echo "   • Get metadata: python cli/main.py metadata VIDEO_URL"
    echo "   • Check health: python cli/main.py health"
    echo "   • View help: python cli/main.py --help"
    echo ""
    echo "📋 Management Commands:"
    echo "   • Stop services: ./scripts/stop_services.sh"
    echo "   • Check status: ./scripts/status_services.sh"
    echo "   • View logs: tail -f logs/*_service.log"
    echo ""
    echo "📚 Documentation:"
    echo "   • User Guide: docs/user-guide.md"
    echo "   • API Documentation: docs/api-documentation.md"
    echo "   • Deployment Guide: docs/deployment-guide.md"
    echo ""
}

# Main function
main() {
    echo "============================================"
    echo "YTArchive Services Startup"
    echo "============================================"
    echo ""

    check_prerequisites
    echo ""

    start_all_services
    echo ""

    show_status

    show_usage_info

    success "YTArchive services are ready!"
}

# Handle script arguments
case "${1:-}" in
    status)
        show_status
        exit 0
        ;;
    health)
        log "Checking health of all services..."
        failed_health_checks=0
        for service in "${!SERVICES[@]}"; do
            port=${SERVICES[$service]}
            if ! check_service_health $service $port; then
                ((failed_health_checks++))
            fi
        done

        if [ $failed_health_checks -eq 0 ]; then
            success "All services are healthy!"
            exit 0
        else
            error "$failed_health_checks service(s) failed health check"
            exit 1
        fi
        ;;
    --help|-h)
        echo "YTArchive Services Startup Script"
        echo ""
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  start    Start all services (default)"
        echo "  status   Show service status"
        echo "  health   Check service health"
        echo "  --help   Show this help message"
        echo ""
        exit 0
        ;;
    start|"")
        main
        ;;
    *)
        error "Unknown command: $1"
        echo "Use '$0 --help' for usage information"
        exit 1
        ;;
esac
