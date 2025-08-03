# Project Status Updates Guide

*Operational procedures for keeping YTArchive planning documents current and accurate*

## Overview

This guide provides step-by-step procedures for maintaining the YTArchive project status documents. For an overview of our documentation architecture and the purpose of each document, see the "Documentation Architecture" section in `PRD.md`.

**Key Documents This Guide Covers**:
- `ImplementationPlan.md` - Current status and next steps
- `CHANGELOG.md` - Historical record of achievements
- Supporting planning documents

---

## Maintenance Workflows

### 🎯 **When Completing a Feature**

1. **Update ImplementationPlan.md**:
   ```markdown
   # Change this:
   - [ ] Feature implementation

   # To this:
   - [x] Feature implementation
   ```

2. **Add to CHANGELOG.md** (if significant):
   ```markdown
   ### 🎉 **FEATURE NAME COMPLETED** (2025-MM-DD)

   #### ✅ **Achievement Summary**
   - Detailed description of what was accomplished
   - Metrics, test counts, technical details

   #### 🔧 **Technical Implementation**
   - Specific technical details
   - Architecture decisions made

   **Related Commits**: `abc1234`, `def5678`, `ghi9012`
   ```

   **💡 Commit ID Best Practice**:
   - Always include git commit IDs at the end of CHANGELOG entries
   - Use `git log --oneline -10` to find recent commit hashes
   - Format as: `**Related Commits**: \`hash1\`, \`hash2\`, \`hash3\``
   - This enables easy traceability and verification of changes

3. **Update Current Status metrics**:
   ```markdown
   # ImplementationPlan.md - Update test counts, completion percentages
   - **Unit Tests**: 210/210 passing (100%)
   - **Service Tests**: 186/186 passing (100%)
   ```

### 🚀 **When Planning New Features**

1. **Add to Future Features in ImplementationPlan.md**:
   ```markdown
   ## Future Features (Backlog)

   ### New Feature Category
   - [ ] **New Feature Name**
     - [ ] Specific implementation task 1
     - [ ] Specific implementation task 2
   ```

2. **Do NOT add to CHANGELOG.md** until the feature is completed

### 📊 **Quarterly Reviews**

**Every 3 months, review and update**:
- ✅ Move completed backlog items from "Future Features" to appropriate completed phase
- ✅ Update roadmap dates and priorities
- ✅ Archive outdated or irrelevant planning items
- ✅ Update test metrics and success criteria

---

## Content Guidelines

### ✅ **Good Practices**

#### For ImplementationPlan.md:
- ✅ **Use checkbox format**: `- [x] Completed item` / `- [ ] Pending item`
- ✅ **Be specific**: "Add playlist download CLI command" not "Improve CLI"
- ✅ **Group logically**: Organize by feature area or implementation phase
- ✅ **Update metrics regularly**: Keep test counts and percentages current
- ✅ **Keep roadmap realistic**: Don't over-commit on future timelines

#### For CHANGELOG.md:
- ✅ **Use descriptive titles**: "COMPREHENSIVE TESTING INFRASTRUCTURE COMPLETE"
- ✅ **Include metrics**: "161/161 tests passing (100% success rate)"
- ✅ **Explain significance**: Why was this milestone important?
- ✅ **Preserve context**: Keep historical details even if they seem verbose
- ✅ **Date everything**: Include completion dates for milestones

### ❌ **Avoid These Mistakes**

#### For ImplementationPlan.md:
- ❌ **Don't include achievement banners**: No "🎉 MILESTONE ACHIEVED" sections
- ❌ **Don't repeat CHANGELOG content**: Keep it concise and forward-focused
- ❌ **Don't leave stale items**: Remove or update outdated tasks regularly
- ❌ **Don't be too granular**: Focus on meaningful feature-level tasks

#### For CHANGELOG.md:
- ❌ **Don't add uncompleted work**: Only document finished achievements
- ❌ **Don't remove historical content**: Preserve the development journey
- ❌ **Don't duplicate ImplementationPlan**: Different purposes, different content

---

## Quick Reference Checklist

### ✅ **After Completing Work**
- [ ] Update ImplementationPlan.md checkboxes `[ ]` → `[x]`
- [ ] Update current status metrics (test counts, etc.)
- [ ] Add achievement to CHANGELOG.md (if significant)
- [ ] Update any affected service specifications
- [ ] Remove completed items from Future Features backlog

### ✅ **Before Starting New Work**
- [ ] Add tasks to ImplementationPlan.md Future Features
- [ ] Review existing guidelines in docs/development-guide.md
- [ ] Check ServiceSpecifications/ for relevant contracts
- [ ] Look at WatchOut/ guides for common patterns

### ✅ **Monthly Maintenance**
- [ ] Review and update roadmap timelines
- [ ] Archive completed items properly
- [ ] Update success metrics and progress indicators
- [ ] Check for stale or outdated content

---

## Best Practices We Learned

### 🎯 **From Our Recent Reorganization**

**What Worked Well**:
- ✅ **Clear document separation**: Each document has a distinct purpose
- ✅ **Checkbox tracking**: Easy to see what's done vs pending
- ✅ **Historical preservation**: All development context preserved in CHANGELOG
- ✅ **Forward focus**: ImplementationPlan stays relevant and actionable

**What to Avoid in Future**:
- ❌ **Document overlap**: Don't duplicate content between files
- ❌ **Stale information**: Update regularly to prevent outdated content
- ❌ **Too much detail in planning**: Keep ImplementationPlan high-level
- ❌ **Losing history**: Don't delete historical context from CHANGELOG

### 🔄 **Sustainable Maintenance**

- **Little and often**: Update documents as work progresses, not in big batches
- **Be consistent**: Use the same formatting and structure patterns
- **Think about readers**: Different audiences need different levels of detail
- **Preserve context**: Future contributors will thank you for detailed history

---

## Templates

### 📋 **New Feature Template (ImplementationPlan.md)**
```markdown
### Feature Category Name
- [ ] **Feature Name**
  - [ ] Specific implementation task
  - [ ] Testing and validation
  - [ ] Documentation updates
  - [ ] Integration with existing services
```

### 📜 **Achievement Template (CHANGELOG.md)**
```markdown
### 🎉 **FEATURE NAME COMPLETED** (YYYY-MM-DD)

#### ✅ **Achievement Summary**
- Brief description of what was accomplished
- Key metrics or success indicators

#### 🔧 **Technical Implementation**
- Specific technical details
- Architecture decisions made
- Testing results

#### 📊 **Impact**
- How this contributes to project goals
- Benefits for users or developers
```

---

## Questions or Issues?

If you're unsure about how to maintain these documents:

1. **Look at recent examples** in the documents themselves
2. **Check this guide** for the appropriate workflow
3. **Consider the audience** - who will read this content and why?
4. **When in doubt, preserve context** - it's easier to trim later than to recreate lost information

**Remember**: These documents are living resources that should evolve with the project while maintaining their core purposes and value to contributors.
