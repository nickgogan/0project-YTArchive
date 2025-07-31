# Python/API-Based Project Workflow Guide

## Purpose
This guide captures a proven workflow for developing Python-based API projects using microservices architecture. It's designed for AI architect agents to efficiently create high-quality projects based on Product Owner/Manager inputs.

## Workflow Overview

### Phase Flow
1. **Concept Clarification** → 2. **Requirements Gathering** → 3. **Architecture Design** → 4. **Technical Decisions** → 5. **Document Creation** → 6. **Project Scaffolding** → 7. **Gap Analysis** → 8. **Document Refinement** → 9. **Implementation Planning**

### Key Success Factors
- Ask comprehensive questions early
- Make decisions incrementally
- Document everything, then consolidate
- Focus on MVP first
- Maintain clear service boundaries

## Phase 1: Concept Clarification

### 1.1 Initial Input Analysis
**Trigger**: Product Owner provides project idea

**Actions**:
1. Parse the core concept
2. Identify the problem domain
3. Note any technical constraints mentioned
4. Clarify ambiguities immediately

**Checkpoint**: ✓ Clear understanding of the basic project concept

### 1.2 Project Initialization
**Actions**:
1. Create project directory structure
2. Initialize with appropriate package manager (e.g., `uv init` for Python)
3. Set up basic `pyproject.toml`

## Phase 2: Requirements Gathering

### 2.1 Comprehensive Question Set
**Template Questions**:

1. **Scope & Features**
   - What is the primary purpose of this project?
   - What are the core features for the MVP?
   - What features are explicitly out of scope?
   - Are there any existing systems this needs to integrate with?

2. **Users & Access**
   - Who are the primary users?
   - How will users interact with the system (CLI, API, Web UI)?
   - What level of technical expertise do users have?
   - Is this for personal use or public distribution?

3. **Technical Requirements**
   - What programming language and version?
   - Are there specific libraries or frameworks required?
   - What are the performance requirements?
   - What are the scale expectations?

4. **Data & Storage**
   - What types of data will be processed?
   - What are the storage requirements?
   - Are there any data privacy/security concerns?
   - What about backup and recovery?

5. **External Dependencies**
   - What external APIs or services are needed?
   - Are there rate limits or quotas to consider?
   - What about authentication and API keys?

6. **Error Handling & Recovery**
   - How should the system handle failures?
   - What constitutes a critical vs. recoverable error?
   - Should there be automatic retry mechanisms?

7. **Deployment & Operations**
   - Where will this be deployed?
   - What are the monitoring requirements?
   - How will updates be handled?

8. **Success Metrics**
   - How do we measure success?
   - What are acceptable performance thresholds?
   - What completion rate is expected?

9. **Timeline & Phases**
   - What's the target timeline?
   - Should features be delivered in phases?
   - What constitutes the MVP?

10. **Future Considerations**
    - What features might be added later?
    - Should the architecture accommodate specific future needs?
    - Are there any long-term maintenance considerations?

**Expected Answer Framework**:
- Clear, specific responses
- Quantifiable metrics where possible
- Explicit "not needed" for out-of-scope items
- Technical constraints clearly stated

**Checkpoint**: ✓ All questions answered in a structured document

### 2.2 Generate Initial PRD
**Actions**:
1. Create comprehensive PRD from answers
2. Include:
   - Executive Summary
   - Goals and Non-Goals
   - User Personas
   - Functional Requirements
   - Technical Requirements
   - Success Metrics
   - Risk Mitigation

## Phase 3: Architecture Design

### 3.1 Architecture Questions
**Decision Points**:

1. **Service Architecture**
   - Monolithic vs Microservices?
   - If microservices, what service boundaries?
   - How many services are appropriate?

2. **Communication Patterns**
   - Synchronous (HTTP/REST) vs Asynchronous (Message Queues)?
   - What serialization format (JSON, Protocol Buffers)?
   - Direct service-to-service or through orchestrator?

3. **Data Management**
   - Shared database vs Service-specific storage?
   - File-based vs Database storage?
   - How is data consistency maintained?

4. **API Design**
   - REST vs GraphQL vs gRPC?
   - Versioning strategy?
   - Authentication approach?

5. **Deployment Architecture**
   - Containerized (Docker) vs Process-based?
   - Service discovery mechanism?
   - Configuration management approach?

6. **Development Approach**
   - Monorepo vs Polyrepo?
   - Shared libraries approach?
   - Testing strategy?

**Checkpoint**: ✓ Clear architectural decisions documented

### 3.2 Technical Stack Decisions
**Categories to Decide**:

1. **Core Technologies**
   - Programming language and version
   - Web framework (FastAPI, Flask, Django)
   - Async vs Sync execution model

2. **Dependencies**
   - Package manager (pip, poetry, uv)
   - Dependency version strategy
   - Core libraries needed

3. **Infrastructure**
   - Service ports and naming
   - Logging approach
   - Monitoring strategy

4. **Development Tools**
   - Testing framework
   - Linting and formatting
   - Documentation tools

## Phase 4: Technical Decisions

### 4.1 Additional Architecture Refinements
**Decision Areas**:

1. **Service Coordination**
   - Orchestration vs Choreography
   - Job/Task management approach
   - State management strategy

2. **Error Handling Philosophy**
   - Retry strategies
   - Circuit breaker patterns
   - Failure isolation

3. **Operational Concerns**
   - Logging standards
   - Monitoring and alerting
   - Performance requirements

4. **Security Considerations**
   - Authentication between services
   - Secret management
   - Data encryption needs

### 4.2 Document Decisions
**Actions**:
1. Create/Update Architecture Decisions document
2. Include rationale for each decision
3. Note explicitly rejected alternatives

**Checkpoint**: ✓ All major technical decisions documented with rationale

## Phase 5: Document Creation

### 5.1 Core Documentation Set
**Documents to Create**:

1. **PRD.md** (Product Requirements Document)
   - Business requirements
   - User stories
   - Success criteria

2. **ArchitectureGuide.md**
   - High-level architecture decisions
   - System design overview
   - Decision rationale

3. **ImplementationGuide.md**
   - Technical patterns
   - Coding standards
   - Common utilities

4. **Service Specifications**
   - Individual service responsibilities
   - API contracts
   - Dependencies

### 5.2 Initial Documentation Approach
**Guidance**:
- Start comprehensive, consolidate later
- Err on side of over-documentation initially
- Use consistent formatting and structure
- Include code examples where helpful

## Phase 6: Project Scaffolding

### 6.1 Directory Structure
**Standard Python API Project Structure**:
```
project-root/
├── services/
│   ├── common/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── utils.py
│   │   └── base.py
│   ├── service1/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api.py
│   │   └── models.py
│   └── service2/
│       └── ...
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── scripts/
├── docs/
├── Planning/
│   ├── PRD.md
│   ├── ArchitectureGuide.md
│   ├── ImplementationGuide.md
│   └── ServiceSpecifications/
├── config/
├── pyproject.toml
├── README.md
├── CHANGELOG.md
└── .gitignore
```

### 6.2 Common Components
**Create Shared Elements**:
1. Base service class
2. Common data models (Pydantic)
3. Utility functions
4. Configuration management
5. Logging setup

**Checkpoint**: ✓ Project structure created with common components

## Phase 7: Gap Analysis

### 7.1 Review All Documentation
**Actions**:
1. Read through all created documents
2. Identify:
   - Missing technical details
   - Inconsistencies between documents
   - Unclear service boundaries
   - Undefined error scenarios
   - Missing configuration details

### 7.2 Categorize Gaps
**Categories**:
1. **Must resolve before coding**
   - Core data models
   - Service responsibilities
   - API contracts
   - Error codes

2. **Can defer to implementation**
   - Optimization strategies
   - Advanced features
   - Monitoring details
   - Performance tuning

### 7.3 Address Critical Gaps
**Actions**:
1. Create additional documentation as needed
2. Update existing documents
3. Ensure all services have clear specifications

**Checkpoint**: ✓ All critical gaps addressed

## Phase 8: Document Refinement

### 8.1 Consolidation Strategy
**When to Consolidate**:
- Multiple documents have overlapping content
- Documents serve similar purposes
- Information is scattered and hard to find
- Maintenance becomes difficult

**When to Keep Separate**:
- Clear, distinct purposes
- Different audiences
- Different update frequencies
- Legal or compliance requirements

### 8.2 Consolidation Process
**Actions**:
1. Identify redundant content
2. Create consolidated structure
3. Archive (don't delete) old documents
4. Update references
5. Create clear document hierarchy

**Final Structure Example**:
```
Planning/
├── PRD.md                    # Business requirements
├── ArchitectureGuide.md      # High-level decisions
├── ImplementationGuide.md    # Technical details
├── FutureFeatures.md         # Deferred items
├── ServiceSpecifications/    # Individual services
│   ├── service1.md
│   └── service2.md
└── Archive/                  # Old documents
```

**Checkpoint**: ✓ Clean, hierarchical documentation structure

## Phase 9: Implementation Planning

### 9.1 Create Detailed Implementation Plan
**Components**:
1. **Phases with timelines**
   - Phase 1: Foundation (Week 1)
   - Phase 2: Core Services (Week 2)
   - Phase 3: Integration (Week 3)
   - Phase 4: Polish & Release (Week 4)

2. **Task Breakdown**
   - Daily goals
   - Dependencies clearly marked
   - Critical path identified

3. **Success Criteria**
   - Per phase metrics
   - Go/no-go decisions
   - Quality gates

### 9.2 Risk Mitigation
**Include**:
- Technical risks and mitigations
- Schedule risks and buffers
- External dependency risks

**Checkpoint**: ✓ Actionable implementation plan with clear priorities

## Success Validation

### Phase Checkpoints Summary
1. ✓ Clear project concept understood
2. ✓ Comprehensive requirements gathered
3. ✓ Architecture decisions made and documented
4. ✓ Technical stack and patterns defined
5. ✓ Complete documentation set created
6. ✓ Project structure scaffolded
7. ✓ Gaps identified and addressed
8. ✓ Documentation consolidated and organized
9. ✓ Implementation plan created

### Quality Indicators
- All decisions have documented rationale
- No conflicting information between documents
- Clear service boundaries and responsibilities
- Comprehensive error handling strategy
- Defined success metrics
- Actionable implementation plan

## Usage Guide for AI Architects

### Starting a New Project
1. **Receive initial concept** from Product Owner
2. **Work through phases sequentially** - don't skip
3. **Ask all template questions** - even if some seem obvious
4. **Document everything** initially, refine later
5. **Validate checkpoints** before proceeding
6. **Create working code structure** early
7. **Review and refine** iteratively

### Common Pitfalls to Avoid
1. Skipping the comprehensive question phase
2. Making architecture decisions too early
3. Under-documenting decisions and rationale
4. Creating service boundaries that are too fine-grained
5. Not planning for error cases upfront
6. Skipping the gap analysis phase

### Adaptation Guidelines
- For smaller projects: Combine some services, but keep the process
- For larger projects: Add more detail to each phase
- For non-Python projects: Adapt technology-specific sections
- For non-API projects: Focus more on component boundaries

## Conclusion
This workflow represents a battle-tested approach to creating well-architected Python API projects. Following this guide ensures comprehensive planning, clear documentation, and a solid foundation for implementation. The key is asking the right questions early and documenting decisions thoroughly before writing code.
