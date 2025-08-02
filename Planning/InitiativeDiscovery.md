# Initiative Discovery Process

*Research and analysis methodology for complex project initiatives*

## Overview

This document defines the systematic discovery process for researching and analyzing complex project initiatives. The process is designed to be executed by competent researchers or AI agents, producing comprehensive analysis and strategic recommendations for architects and project managers.

## Initiative Kickoff

An initiative begins when a new folder is created in the Planning directory:

**Initiative Naming Convention**: `Planning/<InitiativeName>/`
- Use PascalCase naming (e.g., `ConfigurationRefactor`, `PerformanceOptimization`)
- Name should clearly describe the initiative scope
- Avoid abbreviations or unclear acronyms

**Initial Folder Structure**:
```
Planning/
└── <InitiativeName>/
    ├── prompts/
    │   ├── current_state_analysis_prompt.md
    │   ├── external_research_prompt.md
    │   ├── cross_reference_prompt.md
    │   └── executive_summary_prompt.md
    ├── ResearchToDo.md
    └── Loop1/ (created by researcher)
        └── [research deliverables, feedback, and sign-off files]
```

The presence of the `<InitiativeName>` folder with prompts indicates the initiative is ready for researcher assignment.

## Loop Management

**Loop Structure Purpose**:
- **Track Major Iterations**: Each outer feedback loop gets its own numbered folder (Loop1/, Loop2/, etc.)
- **Preserve Iteration History**: Complete audit trail of all major research cycles
- **Isolate Feedback Cycles**: Clean separation between different rounds of stakeholder review
- **Enable Parallel Comparison**: Easy comparison between different loop approaches

**When to Create New Loops**:
- **Loop1**: Always created initially by researcher
- **Loop2+**: Created when stakeholder feedback requires major rework that can't be addressed through document versioning within the current loop
- **Major Rework Triggers**: Fundamental strategy changes, new research directions, significant scope adjustments

**Loop vs. Document Versioning**:
- **Document Versioning** (`_v2`, `_v3`): Minor refinements, additional evidence, clarifications within same strategic approach
- **New Loop**: Major strategic pivot, completely different research direction, fundamental approach change

## Process Scope & Boundaries

### Research Scope
The Initiative Discovery process covers:
- **Current State Analysis**: Comprehensive understanding of existing implementation vs. requirements
- **External Research**: Deep and wide research of global best practices and solutions
- **Cross-Reference Analysis**: Validation of research findings against project constraints
- **Strategic Recommendations**: High-level recommendations for what should be adopted and why

### Discovery Phase Collaboration
The Discovery phase involves iterative collaboration between researcher, architect, and project manager:
- **Researcher**: Conducts analysis, research, and creates deliverables following feedback loop protocol
- **Architect**: Reviews findings for technical feasibility and alignment with architectural principles
- **Project Manager**: Validates scope, timeline implications, and resource requirements
- **Completion Criteria**: Discovery phase concludes only when both architect and project manager sign off on deliverables

### Post-Discovery Handoff
After Discovery phase sign-off, architects and project managers proceed with:
- Make final architectural decisions and document them
- Break down recommendations into specific tasks and implementation plans
- Create timelines and assign resources for implementation

### Core Principles
- **Systematic Analysis**: Each phase builds on previous findings with concrete deliverables
- **Comprehensive Research**: Deep and wide investigation of industry best practices
- **Project Context Grounding**: Always validate against existing project constraints and decisions
- **Strategic Focus**: Provide high-level recommendations, not detailed implementation plans
- **Evidence-Based**: All recommendations supported by research findings and analysis
- **Iterative Refinement**: Researcher loops back to improve deliverables until quality criteria are met

## Discovery Methodology

### Research Feedback Loop

The discovery process is inherently iterative. Researchers should expect to loop back and refine their work multiple times before achieving handoff quality.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          Discovery Process Flow (with Loop Management)          │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐      ┌──────────────────────────────────────────────────────┐
│ Initiative      │      │                    Loop1/                           │
│ Kickoff         │────► │                                                      │
│ • Create folder │      │  ┌─────────────────┐                                │
│ • Add prompts/  │      │  │  Phase 1:       │                                │
│ • ResearchToDo  │      │  │ Current State   │────┐                           │
└─────────────────┘      │  │   Analysis      │    │                           │
                         │  └─────────────────┘    │                           │
                         │          │              │    INNER LOOP             │
                         │          ▼              │  (Researcher              │
                         │  ┌─────────────────┐    │   Self-Correction)        │
                         │  │  Phase 2:       │    │                           │
                         │  │  External       │────┤                           │
                         │  │   Research      │    │                           │
                         │  └─────────────────┘    │                           │
                         │          │              │                           │
                         │          ▼              │                           │
                         │  ┌─────────────────┐    │                           │
                         │  │  Phase 3:       │    │                           │
                         │  │ Cross-Reference │────┤                           │
                         │  │ & Recommendations│   │                           │
                         │  └─────────────────┘    │                           │
                         │          │              │                           │
                         │          ▼              │                           │
                         │  ┌─────────────────┐    │                           │
                         │  │ Quality Check   │    │                           │
                         │  │ • Criteria Met? │    │                           │
                         │  │ • >90% Alignment│    │                           │
                         │  │ • No Major Gaps │    │                           │
                         │  │ • Good Evidence │    │                           │
                         │  └─────────────────┘    │                           │
                         │          │              │                           │
                         │     ┌────▼────┐         │                           │
                         │     │ Ready?  │         │                           │
                         │     └────┬────┘         │                           │
                         │          │              │                           │
                         │      NO  │  YES         │                           │
                         │          │              │                           │
                         │          │       ┌──────▼──────┐                    │
                         │          │       │  Phase 4:   │                    │
                         │          │       │ Executive   │                    │
                         │          │       │  Summary    │                    │
                         │          │       └─────────────┘                    │
                         │          │              │                           │
                         │          ▼              ▼                           │
                         │  ┌─────────────────┐                                │
                         │  │ Inner Iteration │    STAKEHOLDER REVIEW          │
                         │  │ • Version docs  │    ┌─────────────────┐         │
                         │  │ • Clone & edit  │    │ Architect/PM    │         │
                         │  │ • Update ToDo   │    │ Create feedback_│         │
                         │  │ • Go back to    │    │  YYYY-MM-DD.md  │         │
                         │  │   needed phase  │    └─────────────────┘         │
                         │  └─────────────────┘                                │
                         │          │                      │                   │
                         │          └──────────────────────┤                   │
                         └──────────────────────────────────────────────────────┘
                                                            │
                         ┌──────────────────────────────────┼────────────────────┐
                         │                                  ▼                    │
                         │     OUTER LOOP DECISION                               │
                         │                                                       │
                         │    ┌─────────────────┐      ┌─────────────────┐      │
                         │    │ Minor Changes   │      │ Major Rework    │      │
                         │    │ • Version docs  │      │ • Create Loop2/ │      │
                         │    │   within Loop1/ │      │ • Fresh start   │      │
                         │    │ • Stay in Loop1 │      │ • New approach  │      │
                         │    └─────────────────┘      └─────────────────┘      │
                         │            │                        │                │
                         │            ▼                        ▼                │
                         │    ┌─────────────────┐      ┌─────────────────┐      │
                         │    │ Continue Loop1  │      │   Start Loop2   │      │
                         │    │ Refinements     │      │  (Same Process) │      │
                         │    └─────────────────┘      └─────────────────┘      │
                         │            │                        │                │
                         │            └────────┬───────────────┘                │
                         └─────────────────────────────────────────────────────┘
                                              │
                                              ▼
                                    ┌─────────────────┐
                                    │ COMPLETION:     │
                                    │ Both sign-off   │
                                    │ files present   │
                                    │ • signoff_      │
                                    │   architect_    │
                                    │ • signoff_      │
                                    │   projectMgr_   │
                                    └─────────────────┘
```

### Iteration Protocol

**Document Versioning**:
- Never mutate existing deliverable documents
- Create versioned copies (e.g., `CurrentStateAnalysis_v2.md`)
- Clone and edit the document that needs updates
- Preserve all previous versions for audit trail

**Research Todo Updates**:
- Update ResearchToDo document to capture additional work identified
- Add new external research tasks if gaps are discovered
- Document specific improvements needed in existing deliverables
- Track which documents were updated and why

**Quality Gates**:
- All documented quality criteria must be met for each phase
- Alignment score must be >90% in cross-reference analysis
- No major gaps in analysis or recommendations
- Supporting evidence must be sufficient (decent but not exhaustive)

**Loop Back Triggers**:
- Self-assessment reveals gaps against quality criteria
- Later phases reveal incomplete earlier analysis
- External research exposes new information requiring current state update
- Cross-reference analysis identifies missing project constraints
- Strategic recommendations lack sufficient supporting evidence

### Phase 1: Current State Analysis 🔍

**Purpose**: Comprehensive understanding of existing implementation vs. documented requirements

**Getting Started**:
- Review `prompts/current_state_analysis_prompt.md` for specific guidance and questions
- Use prompt templates to ensure comprehensive coverage of analysis areas

**Researcher Activities**:
1. **Gap Analysis**: Compare actual implementation with documented specifications
2. **Issue Identification**: Catalog specific problems, inconsistencies, and missing features
3. **Severity Assessment**: Rate gaps by impact and complexity
4. **Context Gathering**: Examine related code, configurations, and patterns
5. **Documentation Analysis**: Review all relevant project documents (PRD, ArchitectureGuide, etc.)

**Deliverables**:
- Current state analysis document with comprehensive gap analysis
- Severity-rated issue catalog with specific examples
- Assessment of existing vs. documented capabilities
- Context summary of related systems and constraints

**Quality Criteria**:
- Concrete examples of gaps and issues with evidence
- Clear severity classifications with rationale
- Comprehensive coverage of all related project areas
- Objective assessment without solution bias

**Iteration Triggers**:
- External research reveals gaps in current state understanding
- Cross-reference analysis exposes missing project context
- Quality self-assessment identifies insufficient evidence or examples

### Phase 2: External Research 📚

**Purpose**: Deep and wide research of global best practices and industry solutions

**Getting Started**:
- Review `prompts/external_research_prompt.md` for research direction and focus areas
- Use prompt guidance to ensure comprehensive coverage of industry practices

**Researcher Activities**:
1. **Industry Best Practices Research**: Study current approaches across multiple industries and contexts
2. **Technology Landscape Analysis**: Comprehensive evaluation of available tools, libraries, and frameworks
3. **Architectural Pattern Study**: Examine different architectural approaches and their trade-offs
4. **Case Study Analysis**: Research how similar organizations have solved comparable problems
5. **Trend Analysis**: Identify emerging patterns and future directions in the domain

**Deliverables**:
- Comprehensive research document with global best practices
- Technology landscape analysis with objective comparisons
- Architectural pattern analysis with trade-offs
- Case studies of successful implementations
- Trend analysis and future considerations

**Quality Criteria**:
- Research from authoritative and diverse sources
- Balanced analysis of multiple alternatives
- Evidence-based technology comparisons
- Context-aware recommendations (not one-size-fits-all)
- Clear documentation of sources and methodology

**Iteration Triggers**:
- Cross-reference analysis reveals research gaps or conflicts
- Current state analysis update exposes new research areas needed
- Strategic recommendations lack sufficient supporting research
- Discovery of new industry practices or emerging trends

### Phase 3: Cross-Reference & Strategic Recommendations ✅

**Purpose**: Validate research findings against project constraints and produce strategic recommendations

**Getting Started**:
- Review `prompts/cross_reference_prompt.md` for validation framework and scoring methodology
- Use prompt guidance to ensure systematic project constraint analysis

**Researcher Activities**:
1. **Project Constraint Analysis**: Systematic review of PRD, ArchitectureGuide, RecurringIssuesLog, etc.
2. **Alignment Assessment**: Score research compatibility with existing project decisions
3. **Conflict Identification**: Identify conflicts between research findings and project constraints
4. **Strategic Recommendation Development**: Synthesize analysis into high-level strategic recommendations
5. **Trade-off Analysis**: Document pros/cons of different recommendation approaches

**Deliverables**:
- Cross-reference analysis document with alignment scoring
- Strategic recommendations document with clear rationale
- Trade-off analysis for key decisions
- Risk assessment of recommended approaches
- Summary of conflicts and proposed resolutions

**Quality Criteria**:
- Systematic comparison with all relevant project documents
- Objective alignment scoring with clear methodology (target: >90%)
- Strategic recommendations supported by research evidence
- Clear documentation of trade-offs and decision rationale
- Actionable recommendations at appropriate abstraction level
- No major gaps in analysis or recommendations

**Iteration Triggers**:
- Alignment score below 90% threshold
- Discovery of additional project constraints or requirements
- Strategic recommendations lack sufficient research support
- Major gaps identified in analysis coverage
- Conflicts between recommendations and project realities

### Phase 4: Discovery Review & Sign-off 🤝

**Purpose**: Collaborative review and validation of discovery findings with formal sign-off

**Getting Started**:
- Review `prompts/executive_summary_prompt.md` for summary structure and key elements
- Use prompt guidance to create compelling stakeholder presentation

**Researcher Activities**:
1. **Discovery Package Preparation**: Organize all analysis documents for review
2. **Executive Summary Creation**: Provide concise summary of findings and recommendations
3. **Presentation Preparation**: Prepare findings for architect/project manager review
4. **Stakeholder Collaboration**: Address feedback and iterate based on architect/PM input
5. **Final Refinement**: Incorporate feedback and prepare final deliverable package

**Review Process**:
- **Initial Presentation**: Researcher presents findings to architect and project manager
- **Technical Review**: Architect evaluates technical feasibility and architectural alignment
- **Project Review**: Project manager assesses scope, timeline, and resource implications
- **Stakeholder Feedback**: Architect and project manager create `feedback_YYYY-MM-DD.md` file with comments and requests
- **Researcher Response**: Researcher addresses feedback, creates updated deliverables (versioned), and waits for next feedback
- **Feedback Iteration**: Process repeats until stakeholders are satisfied with deliverables
- **Final Review**: Stakeholders review final deliverables and create sign-off files when approved

**Sign-off Deliverables**:
- Executive summary of key findings and strategic recommendations
- Complete set of analysis documents (Current State + Research + Cross-Reference)
- Stakeholder feedback integration and resolution documentation
- Final presentation materials with stakeholder endorsement

**Discovery Phase Completion Criteria**:
- **Architect Sign-off**: Technical feasibility validated, architectural alignment confirmed
  - Creates `signoff_architect_YYYY-MM-DD.md` file in Discovery folder
- **Project Manager Sign-off**: Scope and resource implications acceptable, timeline realistic
  - Creates `signoff_projectManager_YYYY-MM-DD.md` file in Discovery folder
- **Quality Gates Met**: All research quality criteria satisfied
- **Documentation Complete**: All deliverables finalized and stakeholder-approved
- **Researcher Completion**: Both sign-off files present, ResearchToDo.md updated to reflect completion

**Post-Discovery (Implementation Planning Phase)**:
- Architect documents final architectural decisions in ArchitectureGuide
- Project manager breaks down recommendations into implementation tasks and timeline
- Resources allocated and implementation responsibilities assigned

## Case Study: Configuration Refactor Initiative

### Initiative Context
Started with single ImplementationPlan line: "Configuration file support (deferred to future enhancement)" but recognized need for systematic configuration centralization across the project.

### Phase Execution

#### Phase 1: Current State Analysis ✅ COMPLETED
**Document**: `Planning/ConfigurationRefactor/ConfigurationAnalysisReport.md`

**Key Findings**:
- Major gap between extensive documentation (docs/configuration-reference.md) and minimal implementation
- Services using only basic host/port settings with hardcoded values throughout
- Configuration formats inconsistent (TOML example vs YAML documentation)
- No configuration-related issues found in RecurringIssuesLog (positive validation)

**Impact**: Revealed that configuration centralization was needed infrastructure work, not just CLI enhancement

#### Phase 2: External Research ✅ COMPLETED
**Document**: `Planning/ConfigurationRefactor/ConfigurationArchitectureResearch.md`

**Research Sources**: Industry best practices via Perplexity AI analysis

**Key Recommendations**:
- Pydantic BaseSettings over Dynaconf for FastAPI integration
- TOML format for Python ecosystem alignment
- File-based configuration over centralized config service (right scale for YTArchive)
- FastAPI dependency injection with @lru_cache for performance

**Impact**: Validated approach while providing specific implementation patterns

#### Phase 3: Validation & Cross-Reference ✅ COMPLETED
**Document**: `Planning/ConfigurationRefactor/CrossReferenceAnalysis.md`

**Alignment Score**: 95/100 compatibility with existing project decisions

**Perfect Matches Found**:
- TOML format (ArchitectureGuide already decided on TOML 2024-01-22)
- Environment variables for secrets (PRD security requirements)
- Pydantic integration (existing technology stack)
- Service architecture compatibility (FastAPI + microservices)

**Impact**: High confidence in approach due to excellent alignment with existing decisions

#### Phase 4: Discovery Review & Sign-off ✅ COMPLETED

**Discovery Phase Execution**:
- Researcher organized complete documentation package in `Planning/ConfigurationRefactor/Loop1/`
- Presented findings showing 95/100 alignment score and TOML-based recommendations
- Architect reviewed technical feasibility of Pydantic BaseSettings approach
- Project manager assessed scope and timeline implications of configuration centralization

**Stakeholder Sign-offs**:
- **Architect Sign-off**: Created `signoff_architect_2025-01-31.md` validating single-environment decision and TOML format choice (also documented in ArchitectureGuide)
- **Project Manager Sign-off**: Created `signoff_projectManager_2025-01-31.md` accepting simplified scope from 14 comprehensive tasks to 3 essential research items
- **Timeline Adjustment**: Both sign-offs endorsed reduced implementation timeline from 2-3 weeks to 3-5 days for practical approach
- **Strategic Acceptance**: Both stakeholder sign-off files endorsed TOML-based configuration with Pydantic BaseSettings
- **Researcher Completion**: Updated ResearchToDo.md to mark Discovery phase complete upon detecting both sign-off files

**Impact**: Successful collaborative Discovery phase with dual stakeholder validation enabling confident transition to implementation planning

### Lessons Learned

#### Research Process Strengths
1. **Systematic Documentation**: Each phase produced concrete deliverables preventing analysis gaps
2. **External Validation**: Perplexity research provided objective validation of industry approaches
3. **Project Grounding**: Cross-reference analysis kept recommendations realistic and implementable
4. **Strategic Focus**: High-level recommendations allowed architects flexibility in implementation decisions
5. **Evidence-Based**: All recommendations supported by comprehensive research and analysis

#### Key Success Factors
1. **Multi-Source Validation**: Current state + external research + project constraints provided comprehensive view
2. **Concrete Deliverables**: Documentation requirements prevented vague or unsupported recommendations
3. **Alignment Scoring**: Objective measures (95/100) provided confidence in recommendation validity
4. **Clear Handoff**: Structured transition from research to architectural decision-making
5. **Appropriate Abstraction**: Strategic recommendations at right level for architect decision-making

#### Research Process Improvements Identified
1. **Scope Boundary Setting**: Earlier clarification of research scope vs. implementation planning
2. **Stakeholder Engagement**: Regular validation points with architects during research process
3. **Recommendation Formatting**: Standardized format for strategic recommendations
4. **Iterative Quality Control**: Implement feedback loop with document versioning for quality improvements
5. **Early Quality Gates**: Regular self-assessment against quality criteria to trigger iterations sooner

## Application Guidelines

### When to Use This Process
- **Complex initiatives** requiring architectural or strategic decisions
- **Cross-cutting changes** affecting multiple services or components
- **Technology selection** or major library/framework evaluation
- **Process improvements** affecting development workflow
- **Legacy system modernization** or major refactoring initiatives

### When NOT to Use This Process
- **Simple bug fixes** or straightforward feature additions
- **Well-defined tasks** with clear implementation paths
- **Time-critical fixes** requiring immediate action
- **Experimental prototypes** or proof-of-concepts

### Process Adaptation
The methodology can be adapted based on initiative complexity:

**Lightweight Version** (Simpler initiatives):
- Combine phases 1-2 into single analysis document
- Streamlined cross-reference analysis focused on key constraints
- Abbreviated handoff with summary recommendations

**Standard Version** (Most initiatives):
- Full 4-phase process as documented
- Comprehensive research and analysis
- Formal handoff with complete documentation package

**Extended Version** (Highly complex initiatives):
- Add stakeholder validation points during research phases
- Include prototype/proof-of-concept development
- Enhanced risk assessment and multiple recommendation scenarios

### Success Metrics for Discovery Process
- **Research Comprehensiveness**: Coverage of relevant industry practices and alternatives
- **Alignment Score**: Research compatibility with existing project decisions (target: >90%)
- **Recommendation Quality**: Strategic recommendations are actionable and well-supported
- **Handoff Effectiveness**: Architects can make informed decisions based on discovery findings
- **Decision Support**: Discovery provides sufficient evidence for confident architectural decisions

## Templates and Tools

### Research Tools and Techniques
- **Perplexity AI**: For comprehensive industry best practices research and technology comparison
- **Cross-reference analysis**: Systematic comparison with all relevant project documents
- **Alignment scoring**: Quantitative validation of research compatibility with project constraints
- **Evidence documentation**: Clear tracking of sources and research methodology

### Documentation Standards
Each discovery phase should produce documentation following established patterns:
- Use consistent markdown formatting with clear structure
- Include date tracking and research methodology
- Provide executive summaries for each major finding
- Document all sources and research rationale
- Maintain objective, evidence-based tone

### Prompts and Templates

**Prompts Folder Purpose**:
- Provides structured guidance for research agents
- Ensures consistent approach across different initiatives
- Contains specific questions and frameworks for each research phase
- Helps researchers avoid missing critical analysis areas

**Prompt File Contents**:
- **`current_state_analysis_prompt.md`**: Questions for gap analysis, severity assessment, context gathering
- **`external_research_prompt.md`**: Research directions, sources to explore, analysis frameworks
- **`cross_reference_prompt.md`**: Validation methodology, scoring criteria, constraint identification
- **`executive_summary_prompt.md`**: Summary structure, key elements, stakeholder communication

**Using Prompts**:
- Researchers should review relevant prompt file before starting each phase
- Prompts provide guidance, not rigid requirements - adapt to initiative specifics
- Update prompts based on lessons learned from completed initiatives

### Documentation Organization

**Complete Folder Structure**:
```
Planning/
└── <InitiativeName>/
    ├── prompts/
    │   ├── current_state_analysis_prompt.md
    │   ├── external_research_prompt.md
    │   ├── cross_reference_prompt.md
    │   └── executive_summary_prompt.md
    ├── ResearchToDo.md (updated with each iteration, shared across all loops)
    ├── Loop1/
    │   ├── CurrentStateAnalysis.md
    │   ├── CurrentStateAnalysis_v2.md (iterations within loop)
    │   ├── ExternalResearch.md
    │   ├── ExternalResearch_v2.md (iterations within loop)
    │   ├── CrossReferenceAnalysis.md
    │   ├── CrossReferenceAnalysis_v2.md (iterations within loop)
    │   ├── ExecutiveSummary.md (final deliverable for this loop)
    │   ├── feedback_YYYY-MM-DD.md (stakeholder feedback)
    │   ├── feedback_YYYY-MM-DD_v2.md (additional feedback rounds)
    │   ├── signoff_architect_YYYY-MM-DD.md (architect approval)
    │   └── signoff_projectManager_YYYY-MM-DD.md (project manager approval)
    ├── Loop2/ (created if major rework needed)
    │   ├── CurrentStateAnalysis.md (fresh approach)
    │   ├── ExternalResearch.md (new research direction)
    │   ├── CrossReferenceAnalysis.md (revised analysis)
    │   ├── ExecutiveSummary.md (updated recommendations)
    │   ├── feedback_YYYY-MM-DD.md
    │   ├── signoff_architect_YYYY-MM-DD.md
    │   └── signoff_projectManager_YYYY-MM-DD.md
    └── Loop3/ (if additional iterations needed)
        └── [same structure as previous loops]
```

**Naming Conventions**:
- **Initiative Folder**: Use PascalCase (e.g., `ConfigurationRefactor`, `PerformanceOptimization`)
- **Loop Folders**: Use `Loop1/`, `Loop2/`, `Loop3/`, etc. for major iteration tracking
- **Research Documents**: Use descriptive phase names: `CurrentStateAnalysis.md`, `ExternalResearch.md`, `CrossReferenceAnalysis.md`
- **Version Control**: Use `_v2`, `_v3` suffixes for document iterations within a loop
- **Research Tracking**: Maintain `ResearchToDo.md` at initiative level (shared across all loops)
- **Prompt Files**: Use lowercase with underscores: `current_state_analysis_prompt.md`
- **Final Deliverables**: `ExecutiveSummary.md` (one per loop)
- **Feedback Files**: `feedback_YYYY-MM-DD.md` (with `_v2`, `_v3` for additional rounds within loop)
- **Sign-off Files**: `signoff_architect_YYYY-MM-DD.md` and `signoff_projectManager_YYYY-MM-DD.md` (one per loop)

**Archive Management**:
- Preserve all document versions within each loop for audit trail and learning
- Maintain complete loop folders after initiative completion
- Reference completed loops for future initiative guidance
- Each loop provides complete context for understanding iteration evolution
- Final successful loop represents approved strategic direction

### Iteration Management

**Inner Loop (Researcher Self-Iteration)**:
- **Document Versioning**: Never mutate original documents, always create versioned copies
- **Research Todo Tracking**: Update ResearchToDo.md with each iteration cycle
- **Quality Assessment**: Regular self-evaluation against documented quality criteria
- **Loop Decision**: Clear decision points for when to iterate vs. proceed to stakeholder review

**Outer Loop (Stakeholder Feedback Cycle)**:
- **Feedback Monitoring**: Monitor Discovery folder for new `feedback_YYYY-MM-DD.md` files
- **Response Protocol**: Address all feedback points, create updated deliverables, update ResearchToDo.md
- **Wait State**: Researcher waits for next feedback or sign-off files after addressing current feedback
- **Completion Tracking**: Monitor Discovery folder for presence of both sign-off files
- **Final Update**: Update ResearchToDo.md when both sign-off files are present to mark Discovery complete

**Audit Trail**: Maintain complete history of all iterations and stakeholder feedback cycles

### Discovery Collaboration Protocols

**Review Meetings**:
- Schedule formal review sessions with both architect and project manager
- Present findings in structured format with clear recommendations
- Document all feedback and concerns raised during review
- Iterate on deliverables based on stakeholder input

**Stakeholder Feedback Process**:
- **Feedback File Creation**: Architect and project manager collaborate to create `feedback_YYYY-MM-DD.md` file
- **Researcher Response Cycle**: Researcher addresses feedback, creates updated deliverables, then waits for next feedback
- **Feedback File Naming**: Use ISO date format (YYYY-MM-DD) for when feedback was provided
- **Multiple Rounds**: Additional feedback files created as `feedback_YYYY-MM-DD_v2.md`, etc. if needed

**Sign-off Process**:
- **Technical Sign-off**: Architect confirms technical feasibility and architectural alignment
- **Project Sign-off**: Project manager validates scope, timeline, and resource implications
- **File Creation**: Each stakeholder creates individual sign-off file upon approval
- **Completion Gate**: Discovery phase complete only when both sign-off files are present

**Sign-off File Naming Convention**:
- **Architect**: `signoff_architect_YYYY-MM-DD.md` (e.g., `signoff_architect_2025-01-31.md`)
- **Project Manager**: `signoff_projectManager_YYYY-MM-DD.md` (e.g., `signoff_projectManager_2025-01-31.md`)
- **Date Format**: Use ISO date format (YYYY-MM-DD) for the approval date

**Sign-off File Content Template**:
Each sign-off file should follow this structure:
```markdown
# Discovery Phase Sign-off

**Date**: YYYY-MM-DD
**Stakeholder**: [Name], [Role - Architect/Project Manager]
**Initiative**: [Initiative Name]

## Approval Summary
[Brief summary of what was reviewed and approved]

## Key Findings Endorsed
- [Strategic recommendation 1]
- [Strategic recommendation 2]
- [etc.]

## Implementation Conditions/Notes
[Any conditions, constraints, or notes for implementation phase]

## Formal Approval
☑️ I approve the Discovery phase deliverables and strategic recommendations for this initiative.

**Signed**: [Name]
**Date**: [Date]
```

**Feedback File Content Template**:
```markdown
# Discovery Phase Feedback

**Date**: YYYY-MM-DD
**Reviewers**: [Architect Name], [Project Manager Name]
**Initiative**: [Initiative Name]

## Overall Assessment
[High-level feedback on deliverables quality and completeness]

## Specific Feedback by Document

### Current State Analysis
- [Feedback point 1]
- [Feedback point 2]

### External Research
- [Feedback point 1]
- [Feedback point 2]

### Cross-Reference Analysis
- [Feedback point 1]
- [Feedback point 2]

### Executive Summary
- [Feedback point 1]
- [Feedback point 2]

## Action Items for Researcher
- [ ] [Specific action item 1]
- [ ] [Specific action item 2]
- [ ] [etc.]

## Questions for Clarification
- [Question 1]
- [Question 2]

## Next Steps
[What the researcher should do next - iterate, clarify, or prepare for final review]
```

**Researcher Response Protocol**:
1. **Monitor for Feedback**: Check for new `feedback_YYYY-MM-DD.md` files in current loop folder
2. **Analyze Feedback**: Review all feedback points and action items thoroughly
3. **Assess Scope of Changes**: Determine if feedback requires minor refinements or major rework
4. **Choose Response Strategy**:
   - **Minor Changes**: Update existing documents with version suffixes (`_v2`, `_v3`)
   - **Major Rework**: Create new loop folder (Loop2/, Loop3/, etc.) and start fresh
5. **Update ResearchToDo**: Add specific tasks based on feedback requirements (at initiative level)
6. **Address Feedback**: Work through action items systematically
7. **Document Updates**: Create appropriate document versions or new loop documents
8. **Iterate Until Ready**: Continue refining until ready for next review cycle
9. **Wait for Next Feedback**: Monitor for additional feedback or final sign-off files in current loop

**Researcher Completion Criteria**:
- Check current loop folder for presence of both sign-off files
- When both files exist, update ResearchToDo.md to mark Discovery phase as complete
- Discovery phase is considered finished and researcher's job is done
- All loop folders remain as permanent archive of the initiative discovery process

**Stakeholder Collaboration**:
- Maintain regular communication during iteration cycles
- Address concerns promptly and document resolution approaches
- Remain available for clarification questions throughout Discovery phase
- Facilitate consensus between architect and project manager perspectives

---

## Conclusion

The Initiative Discovery Process provides a systematic, repeatable research methodology for complex project initiatives. It ensures comprehensive analysis while maintaining clear boundaries between research/analysis and implementation planning.

**Key Benefits**:
- **Comprehensive Research**: Multi-phase approach prevents critical oversights in analysis
- **Strategic Focus**: High-level recommendations allow architectural flexibility
- **Evidence-Based**: All recommendations supported by thorough research and validation
- **Clear Handoff**: Structured transition from research to architectural decision-making
- **Repeatable Methodology**: Clear process can be applied consistently across initiatives

**Discovery Phase Deliverable Package**:
- Current State Analysis document (with iterations)
- External Research document with industry best practices (with iterations)
- Cross-Reference Analysis with alignment scoring (with iterations)
- Executive Summary with strategic recommendations
- All stakeholder feedback files: `feedback_YYYY-MM-DD.md` (with iterations)
- Architect sign-off file: `signoff_architect_YYYY-MM-DD.md`
- Project Manager sign-off file: `signoff_projectManager_YYYY-MM-DD.md`
- Updated ResearchToDo.md marking Discovery phase completion
- Complete Discovery folder with audit trail of all iterations and feedback cycles

**Post-Discovery Implementation Planning**:
- Architect makes final architectural decisions and documents them in ArchitectureGuide
- Project manager breaks down strategic recommendations into specific implementation tasks
- Create detailed timelines and assign resources for implementation
- Track implementation progress against Discovery phase recommendations
- Reference Discovery documentation for implementation guidance and context

---

**Process Version**: 1.0
**Last Updated**: January 31, 2025
**Case Studies**: 1 (Configuration Refactor)
**Status**: Proven research methodology ready for broader application
