#!/bin/bash

# YTArchive Services Status Script
# Displays comprehensive status information for all YTArchive services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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
    echo -e "${BLUE}[STATUS]${NC} $1"
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

info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

# Check if service is running
check_service_running() {
    local service=$1
    local pid_file="$PID_DIR/${service}_service.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat $pid_file)
        if kill -0 $pid 2>/dev/null; then
            echo "$pid"
            return 0
        else
            # Stale PID file
            rm -f $pid_file 2>/dev/null || true
            echo ""
            return 1
        fi
    else
        echo ""
        return 1
    fi
}

# Check service health via HTTP
check_service_health() {
    local service=$1
    local port=$2

    local response=$(curl -s --max-time 3 "http://localhost:$port/health" 2>/dev/null || echo "")

    if [ -n "$response" ]; then
        echo "$response"
        return 0
    else
        echo ""
        return 1
    fi
}

# Get service memory usage
get_service_memory() {
    local pid=$1

    if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
        local memory=$(ps -o rss= -p $pid 2>/dev/null | tr -d ' ')
        if [ -n "$memory" ]; then
            # Convert KB to MB
            echo "scale=1; $memory / 1024" | bc 2>/dev/null || echo "0.0"
        else
            echo "0.0"
        fi
    else
        echo "0.0"
    fi
}

# Get service CPU usage
get_service_cpu() {
    local pid=$1

    if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
        local cpu=$(ps -o %cpu= -p $pid 2>/dev/null | tr -d ' ')
        if [ -n "$cpu" ]; then
            echo "$cpu"
        else
            echo "0.0"
        fi
    else
        echo "0.0"
    fi
}

# Get service uptime
get_service_uptime() {
    local pid=$1

    if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
        local start_time=$(ps -o lstart= -p $pid 2>/dev/null)
        if [ -n "$start_time" ]; then
            local start_epoch=$(date -j -f "%a %b %d %T %Y" "$start_time" "+%s" 2>/dev/null || echo "0")
            local current_epoch=$(date +%s)
            local uptime_seconds=$((current_epoch - start_epoch))

            if [ $uptime_seconds -lt 60 ]; then
                echo "${uptime_seconds}s"
            elif [ $uptime_seconds -lt 3600 ]; then
                echo "$((uptime_seconds / 60))m $((uptime_seconds % 60))s"
            elif [ $uptime_seconds -lt 86400 ]; then
                echo "$((uptime_seconds / 3600))h $((uptime_seconds % 3600 / 60))m"
            else
                echo "$((uptime_seconds / 86400))d $((uptime_seconds % 86400 / 3600))h"
            fi
        else
            echo "unknown"
        fi
    else
        echo "0s"
    fi
}

# Get log file size
get_log_size() {
    local service=$1
    local log_file="$LOG_DIR/${service}_service.log"

    if [ -f "$log_file" ]; then
        local size=$(stat -f%z "$log_file" 2>/dev/null || echo "0")
        if [ $size -lt 1024 ]; then
            echo "${size}B"
        elif [ $size -lt 1048576 ]; then
            echo "$((size / 1024))KB"
        else
            echo "$(echo "scale=1; $size / 1048576" | bc)MB"
        fi
    else
        echo "0B"
    fi
}

# Display detailed service status
show_detailed_status() {
    echo "============================================"
    echo "YTArchive Services - Detailed Status"
    echo "============================================"
    echo "$(date)"
    echo ""

    local running_count=0
    local healthy_count=0
    local total_memory=0

    printf "%-12s %-8s %-10s %-12s %-8s %-6s %-10s %-8s\n" \
           "SERVICE" "STATUS" "HEALTH" "PID" "UPTIME" "CPU%" "MEMORY" "LOG SIZE"
    echo "--------------------------------------------------------------------------------"

    for service in jobs metadata download storage; do
        local port=${SERVICES[$service]}
        local pid=$(check_service_running $service)
        local status=""
        local health=""
        local memory="0.0"
        local cpu="0.0"
        local uptime="0s"
        local log_size=$(get_log_size $service)

        if [ -n "$pid" ]; then
            status="${GREEN}RUNNING${NC}"
            running_count=$((running_count + 1))

            memory=$(get_service_memory $pid)
            cpu=$(get_service_cpu $pid)
            uptime=$(get_service_uptime $pid)
            total_memory=$(echo "$total_memory + $memory" | bc)

            # Check health
            local health_response=$(check_service_health $service $port)
            if [ -n "$health_response" ]; then
                health="${GREEN}HEALTHY${NC}"
                healthy_count=$((healthy_count + 1))
            else
                health="${YELLOW}UNHEALTHY${NC}"
            fi
        else
            status="${RED}STOPPED${NC}"
            health="${RED}N/A${NC}"
            pid="N/A"
        fi

        printf "%-12s %-18s %-20s %-12s %-8s %-6s %-10s %-8s\n" \
               "$service" "$status" "$health" "$pid" "$uptime" "${cpu}%" "${memory}MB" "$log_size"
    done

    echo ""
    echo "Summary:"
    echo "--------"
    echo "Running Services: $running_count/4"
    echo "Healthy Services: $healthy_count/4"
    echo "Total Memory Usage: ${total_memory}MB"
    echo ""
}

# Show service endpoints
show_endpoints() {
    echo "Service Endpoints:"
    echo "------------------"

    for service in jobs metadata download storage; do
        local port=${SERVICES[$service]}
        local pid=$(check_service_running $service)

        if [ -n "$pid" ]; then
            local health_response=$(check_service_health $service $port)
            if [ -n "$health_response" ]; then
                echo -e "✅ $service: http://localhost:$port (${GREEN}accessible${NC})"
            else
                echo -e "⚠️  $service: http://localhost:$port (${YELLOW}unreachable${NC})"
            fi
        else
            echo -e "❌ $service: http://localhost:$port (${RED}stopped${NC})"
        fi
    done
    echo ""
}

# Show recent log entries
show_recent_logs() {
    local service=$1
    local lines=${2:-10}

    echo "Recent logs for $service service (last $lines lines):"
    echo "----------------------------------------------------"

    local log_file="$LOG_DIR/${service}_service.log"
    if [ -f "$log_file" ]; then
        tail -n $lines "$log_file" | while IFS= read -r line; do
            # Color-code log levels
            if [[ $line == *"ERROR"* ]]; then
                echo -e "${RED}$line${NC}"
            elif [[ $line == *"WARNING"* ]]; then
                echo -e "${YELLOW}$line${NC}"
            elif [[ $line == *"INFO"* ]]; then
                echo -e "${GREEN}$line${NC}"
            else
                echo "$line"
            fi
        done
    else
        echo "Log file not found: $log_file"
    fi
    echo ""
}

# Check system resources
check_system_resources() {
    echo "System Resources:"
    echo "-----------------"

    # CPU usage
    local cpu_usage=$(top -l 1 -n 0 | grep "CPU usage" | awk '{print $3}' | sed 's/%//')
    echo "System CPU Usage: ${cpu_usage}%"

    # Memory usage
    local memory_info=$(vm_stat)
    local page_size=$(vm_stat | head -1 | awk '{print $8}')
    local free_pages=$(echo "$memory_info" | grep "Pages free" | awk '{print $3}' | sed 's/\.//')
    local active_pages=$(echo "$memory_info" | grep "Pages active" | awk '{print $3}' | sed 's/\.//')
    local inactive_pages=$(echo "$memory_info" | grep "Pages inactive" | awk '{print $3}' | sed 's/\.//')
    local wired_pages=$(echo "$memory_info" | grep "Pages wired down" | awk '{print $4}' | sed 's/\.//')

    local total_mb=$(((free_pages + active_pages + inactive_pages + wired_pages) * page_size / 1048576))
    local used_mb=$(((active_pages + inactive_pages + wired_pages) * page_size / 1048576))

    echo "System Memory: ${used_mb}MB used / ${total_mb}MB total"

    # Disk usage for YTArchive directories
    if [ -d "downloads" ]; then
        local downloads_size=$(du -sh downloads 2>/dev/null | awk '{print $1}')
        echo "Downloads Directory: $downloads_size"
    fi

    if [ -d "storage" ]; then
        local storage_size=$(du -sh storage 2>/dev/null | awk '{print $1}')
        echo "Storage Directory: $storage_size"
    fi

    if [ -d "logs" ]; then
        local logs_size=$(du -sh logs 2>/dev/null | awk '{print $1}')
        echo "Logs Directory: $logs_size"
    fi

    echo ""
}

# Main status display
main() {
    # Check if we're in the right directory
    if [ ! -f "pyproject.toml" ] || [ ! -d "services" ]; then
        error "Please run this script from the YTArchive root directory"
        exit 1
    fi

    show_detailed_status
    show_endpoints
    check_system_resources
}

# Handle script arguments
case "${1:-}" in
    logs)
        service_name=${2:-"all"}
        lines=${3:-10}

        if [ "$service_name" == "all" ]; then
            for service in jobs metadata download storage; do
                show_recent_logs $service $lines
            done
        elif [ -n "${SERVICES[$service_name]}" ]; then
            show_recent_logs $service_name $lines
        else
            error "Unknown service: $service_name"
            echo "Available services: ${!SERVICES[*]}"
            exit 1
        fi
        ;;
    watch)
        # Watch mode - refresh every 3 seconds
        while true; do
            clear
            main
            echo "Press Ctrl+C to stop watching..."
            sleep 3
        done
        ;;
    simple)
        # Simple status display
        echo "YTArchive Services Status:"
        for service in "${!SERVICES[@]}"; do
            local pid=$(check_service_running $service)
            if [ -n "$pid" ]; then
                echo -e "  $service: ${GREEN}RUNNING${NC} (PID: $pid)"
            else
                echo -e "  $service: ${RED}STOPPED${NC}"
            fi
        done
        ;;
    --help|-h)
        echo "YTArchive Services Status Script"
        echo ""
        echo "Usage: $0 [COMMAND] [OPTIONS]"
        echo ""
        echo "Commands:"
        echo "  status          Show detailed status (default)"
        echo "  simple          Show simple status"
        echo "  watch           Watch status with auto-refresh"
        echo "  logs [SERVICE] [LINES]  Show recent log entries"
        echo "  --help          Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                    # Detailed status"
        echo "  $0 simple           # Simple status"
        echo "  $0 watch            # Watch mode"
        echo "  $0 logs             # All service logs (10 lines)"
        echo "  $0 logs jobs 20     # Jobs service logs (20 lines)"
        echo ""
        exit 0
        ;;
    ""|-s|status)
        main
        ;;
    *)
        error "Unknown command: $1"
        echo "Use '$0 --help' for usage information"
        exit 1
        ;;
esac
