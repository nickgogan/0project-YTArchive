#!/bin/bash

# YTArchive Services Stop Script
# Gracefully stops all YTArchive microservices

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PID_DIR="pids"
LOG_DIR="logs"

# Service configurations
declare -A SERVICES=(
    ["jobs"]="8001"
    ["metadata"]="8002"
    ["download"]="8003"
    ["storage"]="8004"
)

# Logging functions
log() {
    echo -e "${BLUE}[STOP]${NC} $1"
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

# Stop a single service
stop_service() {
    local service=$1
    local port=$2

    log "Stopping $service service..."

    local pid_file="$PID_DIR/${service}_service.pid"

    if [ ! -f "$pid_file" ]; then
        warning "$service service PID file not found - may not be running"
        return 0
    fi

    local pid=$(cat $pid_file)

    # Check if process is still running
    if ! kill -0 $pid 2>/dev/null; then
        warning "$service service (PID: $pid) is not running - cleaning up PID file"
        rm -f $pid_file
        return 0
    fi

    # Try graceful shutdown first
    log "Sending TERM signal to $service service (PID: $pid)"
    if kill -TERM $pid 2>/dev/null; then
        # Wait for graceful shutdown (up to 10 seconds)
        local attempts=10
        while [ $attempts -gt 0 ] && kill -0 $pid 2>/dev/null; do
            echo -n "."
            sleep 1
            ((attempts--))
        done
        echo ""

        # Check if process is still running
        if kill -0 $pid 2>/dev/null; then
            warning "$service service did not respond to TERM signal, sending KILL signal"
            kill -KILL $pid 2>/dev/null || true
            sleep 2
        fi
    fi

    # Verify process is stopped
    if kill -0 $pid 2>/dev/null; then
        error "Failed to stop $service service (PID: $pid)"
        return 1
    else
        success "$service service stopped"
        rm -f $pid_file
        return 0
    fi
}

# Stop all services
stop_all_services() {
    log "Stopping YTArchive services..."

    local failed_stops=()

    # Stop services in reverse dependency order
    for service in storage download metadata jobs; do
        if ! stop_service $service ${SERVICES[$service]}; then
            failed_stops+=($service)
        fi
        echo ""
    done

    # Report results
    if [ ${#failed_stops[@]} -eq 0 ]; then
        success "All services stopped successfully!"
        return 0
    else
        error "Failed to stop services: ${failed_stops[*]}"
        return 1
    fi
}

# Force stop all services (kill -9)
force_stop() {
    log "Force stopping all YTArchive services..."

    for service in "${!SERVICES[@]}"; do
        local pid_file="$PID_DIR/${service}_service.pid"

        if [ -f "$pid_file" ]; then
            local pid=$(cat $pid_file)

            if kill -0 $pid 2>/dev/null; then
                log "Force killing $service service (PID: $pid)"
                kill -KILL $pid 2>/dev/null || true
                success "$service service force stopped"
            else
                log "$service service was not running"
            fi

            rm -f $pid_file
        else
            log "$service service PID file not found"
        fi
    done

    success "Force stop completed"
}

# Clean up orphaned processes
cleanup_orphaned() {
    log "Cleaning up orphaned YTArchive processes..."

    # Find processes by command pattern
    local found_processes=0

    for service in "${!SERVICES[@]}"; do
        local port=${SERVICES[$service]}
        local service_pattern="services/$service/main.py.*--port $port"

        # Find processes matching the service pattern
        local pids=$(pgrep -f "$service_pattern" 2>/dev/null || true)

        if [ -n "$pids" ]; then
            log "Found orphaned $service service processes: $pids"
            echo $pids | xargs kill -TERM 2>/dev/null || true
            sleep 2

            # Check if any are still running and kill them
            local remaining_pids=$(pgrep -f "$service_pattern" 2>/dev/null || true)
            if [ -n "$remaining_pids" ]; then
                warning "Force killing remaining $service processes: $remaining_pids"
                echo $remaining_pids | xargs kill -KILL 2>/dev/null || true
            fi

            found_processes=1
        fi
    done

    if [ $found_processes -eq 1 ]; then
        success "Orphaned process cleanup completed"
    else
        log "No orphaned processes found"
    fi

    # Clean up stale PID files
    if [ -d "$PID_DIR" ]; then
        find $PID_DIR -name "*_service.pid" -type f -delete 2>/dev/null || true
    fi
}

# Display current status
show_status() {
    echo ""
    echo "============================================"
    echo "YTArchive Services Status"
    echo "============================================"

    local running_count=0

    for service in "${!SERVICES[@]}"; do
        local port=${SERVICES[$service]}
        local pid_file="$PID_DIR/${service}_service.pid"

        echo -n "$service service (port $port): "

        if [ -f "$pid_file" ]; then
            local pid=$(cat $pid_file)
            if kill -0 $pid 2>/dev/null; then
                echo -e "${YELLOW}RUNNING${NC} (PID: $pid)"
                ((running_count++))
            else
                echo -e "${RED}STOPPED${NC} (stale PID file)"
                rm -f $pid_file 2>/dev/null || true
            fi
        else
            echo -e "${GREEN}STOPPED${NC}"
        fi
    done

    echo ""

    if [ $running_count -eq 0 ]; then
        success "All services are stopped"
    else
        warning "$running_count service(s) still running"
    fi
}

# Main function
main() {
    echo "============================================"
    echo "YTArchive Services Stop"
    echo "============================================"
    echo ""

    stop_all_services
    echo ""

    show_status

    log "Services shutdown completed"
}

# Handle script arguments
case "${1:-}" in
    status)
        show_status
        exit 0
        ;;
    force)
        echo "============================================"
        echo "YTArchive Services Force Stop"
        echo "============================================"
        echo ""
        force_stop
        echo ""
        show_status
        exit 0
        ;;
    cleanup)
        echo "============================================"
        echo "YTArchive Orphaned Process Cleanup"
        echo "============================================"
        echo ""
        cleanup_orphaned
        echo ""
        show_status
        exit 0
        ;;
    --help|-h)
        echo "YTArchive Services Stop Script"
        echo ""
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  stop     Gracefully stop all services (default)"
        echo "  force    Force kill all services immediately"
        echo "  cleanup  Clean up orphaned processes and stale PID files"
        echo "  status   Show current service status"
        echo "  --help   Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                  # Graceful stop"
        echo "  $0 force           # Force stop all services"
        echo "  $0 cleanup         # Clean up orphaned processes"
        echo ""
        exit 0
        ;;
    stop|"")
        main
        ;;
    *)
        error "Unknown command: $1"
        echo "Use '$0 --help' for usage information"
        exit 1
        ;;
esac
