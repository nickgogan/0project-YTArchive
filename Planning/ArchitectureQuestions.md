# YouTube Archive - Architecture Decisions

This document captures the architectural decisions and design choices made for the YouTube Archive project.

## 1. Service Granularity

**Question:** How do you envision the service separation?

- ✅ **Separate processes/microservices that communicate via HTTP/queues**
- ❌ Modules within a monolithic application that act as "services"
- ❌ Hybrid approach

## 2. API Design

**For the REST API:**

### Synchronous vs Asynchronous Operations
- **Current Decision:** Synchronous for now
- **Future Enhancement:** Make operations asynchronous in Phase 2 or 3 (return job ID)

### Long-running Operations
- **Solution:** Jobs service that keeps track of all operations and their states

### Status Updates
- **Current Decision:** Polling for now
- **Future Enhancement:** Add webhooks in Phase 3

## 3. Data Flow

### Metadata Service Integration
- **Decision:** Metadata service must always be called before video download
- **Optimization:** Only persist metadata if it differs from the latest payload
- **Architecture:** Use dedicated metadata service with Jobs service coordination

### Service Architecture
- **Jobs Service:** Captures cross-service work
- **JobExecutor Service:** Executes individual services
- **Data Isolation:** Services are completely isolated (no shared data store)

## 4. Error Handling & Recovery

### Automatic Retries
- **Decision:** Yes, up to 3 attempts using backoff logic
- **Fallback:** Queue for manual retry via Jobs service after 3 failed attempts

### Partial Downloads
- **Decision:** Resume from point of failure

## 5. Configuration Management

### Storage Location
- **Decision:** Local config file with sections for each service
- **Structure:** Each service has its own config section within shared file

### Sensitive Data
- **Decision:** Environment variables for API keys and sensitive settings

## 6. Service Communication

### Current Architecture
- ✅ **Direct HTTP calls between services**
- ❌ Message queue (Redis)
- ❌ File system based communication

### Future Enhancements (Phase 3)
- Shared database option
- Message queue integration

## 7. Logging & Monitoring

### Logging Strategy
- **Decision:** Centralized logging via dedicated Logging service
- **Detail Level:** Info level for progress tracking
- **Metrics:** Services will emit metrics/events

## 8. State Management

### Progress Persistence
- **Decision:** Via the Jobs service

### Download History
- **Decision:** Track via Jobs service

### Duplicate Requests
- **Current:** No duplicate detection
- **Future Enhancement:** Add in Phase 3

## 9. CLI/API Integration

### CLI Architecture
- ✅ **CLI commands directly call service code**
- ❌ CLI goes through REST API

### Authentication
- **Decision:** No authentication between CLI and APIs

## 10. Development Approach

### Architecture Strategy
- ✅ **Design for services from the start**
- ❌ Start monolithic and split later

### Deployment
- **Decision:** Keep it simple - no Docker containers
- **Approach:** Single deployment with separate service processes

---

## Summary

The YouTube Archive will be built as a microservices architecture from day one, with:
- Direct HTTP communication between services
- Centralized job management and logging
- Local configuration with environment variable overrides
- Synchronous operations initially, with async planned for future phases