# Documentation Maintenance Guide

*Ensuring docs/ stays current, accurate, and valuable for users and developers*

## Overview

The `docs/` directory contains six critical documentation files that serve different audiences. This guide provides systematic procedures for keeping them synchronized with the codebase to ensure accuracy and usefulness.

**Key Principle**: Documentation that's out of sync is worse than no documentation - it misleads users and erodes trust.

---

## Documentation Architecture

### 📚 **Document Purposes & Audiences**

| Document | Audience | Purpose | Sync Frequency |
|----------|----------|---------|---------------|
| **user-guide.md** | End users, new adopters | CLI usage, features, quick start | After CLI changes |
| **api-documentation.md** | Developers, integrators | Service APIs, endpoints, data models | After API changes |
| **testing-guide.md** | Contributors, maintainers | Test procedures, infrastructure | After test structure changes |
| **configuration-reference.md** | Ops teams, deployers | All config options, environment vars | After config changes |
| **deployment-guide.md** | Ops teams, production | Production deployment, requirements | After major releases |
| **development-guide.md** | Developers | Technical implementation patterns | After architecture changes |

---

## Critical Synchronization Points

### 🎯 **High-Impact Sync Points** (Must be accurate)

#### 1. **CLI Commands & Options** (`user-guide.md` ↔ `cli/main.py`)
**Why Critical**: Users copy-paste commands directly from documentation.

**Sync Triggers**:
- Adding new CLI commands
- Changing command options or flags
- Modifying help text or descriptions
- Changing default values

**Validation**: Run actual commands from docs to ensure they work.

#### 2. **API Endpoints** (`api-documentation.md` ↔ `services/*/main.py`)
**Why Critical**: Developers build integrations based on this documentation.

**Sync Triggers**:
- Adding/removing API endpoints
- Changing request/response formats
- Modifying error codes or messages
- Changing service ports or URLs

**Validation**: Test API calls with exact examples from documentation.

#### 3. **Configuration Options** (`configuration-reference.md` ↔ service configs)
**Why Critical**: Incorrect config docs can break deployments.

**Sync Triggers**:
- Adding new environment variables
- Changing default values
- Modifying configuration file formats
- Adding/removing service settings

**Validation**: Test configurations against actual service startup.

#### 4. **Test Metrics** (`testing-guide.md`, `deployment-guide.md` ↔ test results)
**Why Critical**: Inaccurate metrics undermine credibility.

**Sync Triggers**:
- Adding new test categories
- Significant changes in test counts
- Major testing infrastructure changes
- Quality milestone achievements

**Validation**: Run actual test commands and compare results.

#### 5. **Development Patterns** (`development-guide.md` ↔ `services/*/`)
**Why Critical**: Developers rely on this for consistent implementation patterns.

**Sync Triggers**:
- Adding new data models or APIs
- Changing service communication patterns
- Updating development standards
- New testing or validation approaches

**Validation**: Verify code examples compile and follow current patterns.

---

## Update Procedures

### 🛠️ **When Adding CLI Commands**

**Files to Update**: `user-guide.md`

**Step-by-step**:

1. **Add to command reference section**:
   ```markdown
   #### New Command Name
   ```bash
   python cli/main.py new-command [options]
   ```

   **Options:**
   - `--option`: Description of what it does
   ```

2. **Add usage examples**:
   ```markdown
   # Basic usage
   python cli/main.py new-command input

   # Advanced usage
   python cli/main.py new-command input --option value
   ```

3. **Update table of contents** if needed

4. **Test every example** you add - run the actual commands

**Template**:
```markdown
#### [Command Name]

**Purpose**: Brief description of what this command does

**Syntax:**
```bash
python cli/main.py command-name [arguments] [options]
```

**Arguments:**
- `argument`: Description and requirements

**Options:**
- `--option, -o`: Description and default value

**Examples:**
```bash
# Basic example with explanation
python cli/main.py command-name basic-arg

# Advanced example with explanation
python cli/main.py command-name complex-arg --option value
```

**Output:**
```
Expected output format example
```
```

### 🔌 **When Adding API Endpoints**

**Files to Update**: `api-documentation.md`

**Step-by-step**:

1. **Add endpoint to appropriate service section**:
   ```markdown
   ### New Endpoint Name
   ```http
   POST /api/v1/new-endpoint
   ```
   ```

2. **Document request format**:
   ```markdown
   **Request Body:**
   ```json
   {
     "required_field": "string",
     "optional_field": "integer"
   }
   ```
   ```

3. **Document response format**:
   ```markdown
   **Response:**
   ```json
   {
     "status": "success",
     "data": {
       "result_field": "value"
     }
   }
   ```
   ```

4. **Add error responses**:
   ```markdown
   **Error Responses:**
   - `400 Bad Request`: Invalid input format
   - `404 Not Found`: Resource not found
   ```

5. **Test with actual service** - make real API calls

**Template**:
```markdown
### [Endpoint Name]

**Purpose**: Brief description of endpoint functionality

```http
[METHOD] /api/v1/endpoint-path
```

**Authentication**: Required/Not required

**Request Headers:**
- `Content-Type: application/json` (if applicable)

**Request Body:**
```json
{
  "field": "type - description"
}
```

**Success Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "field": "value"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Description
- `500 Internal Server Error`: Description

**Example:**
```bash
curl -X POST http://localhost:8001/api/v1/endpoint-path \
  -H "Content-Type: application/json" \
  -d '{"field": "value"}'
```
```

### ⚙️ **When Adding Configuration Options**

**Files to Update**: `configuration-reference.md`

**Step-by-step**:

1. **Add to appropriate section** (Global, Service-specific, etc.)

2. **Add to environment variables table**:
   ```markdown
   | `NEW_VAR_NAME` | Description | type | `default` | range/options |
   ```

3. **Add to YAML configuration example**:
   ```yaml
   service:
     new_setting: default_value
   ```

4. **Test configuration** - start services with new settings

**Template**:
```markdown
#### New Configuration Section

| Variable | Description | Type | Default | Options/Range |
|----------|-------------|------|---------|---------------|
| `VAR_NAME` | Clear description | string/int/bool | `default` | valid values |

**YAML Configuration:**
```yaml
section:
  setting: value
  nested:
    subsetting: value
```

**Example Usage:**
```bash
export VAR_NAME=value
python service/main.py
```

**Notes:**
- Important usage notes
- Warnings about changing defaults
- Performance implications
```

### 🧪 **When Test Structure Changes**

**Files to Update**: `testing-guide.md`, `deployment-guide.md`

**Step-by-step**:

1. **Update test counts** in relevant sections
2. **Update directory structure** if test organization changed
3. **Update test commands** if execution methods changed
4. **Verify test metrics** by running actual test commands

### 🏗️ **When Updating Development Patterns**

**Files to Update**: `development-guide.md`

**Step-by-step**:

1. **Update data models** if new Pydantic models added
2. **Update API standards** if service patterns changed
3. **Update code examples** to reflect current practices
4. **Test code examples** to ensure they work

### 🚀 **When Preparing Releases**

**Files to Update**: `deployment-guide.md`, potentially all others

**Step-by-step**:

1. **Update test metrics** with current results
2. **Update version numbers** throughout documentation
3. **Update system requirements** if they changed
4. **Review all examples** for accuracy
5. **Run full documentation validation** (see checklist below)

---

## Validation Procedures

### ✅ **Documentation Validation Checklist**

**Before committing documentation changes:**

#### CLI Documentation (`user-guide.md`)
- [ ] Run every CLI command example in the documentation
- [ ] Verify all option flags and arguments work as documented
- [ ] Check that output examples match actual output
- [ ] Ensure help text matches what's in the docs

#### API Documentation (`api-documentation.md`)
- [ ] Make actual API calls using documented examples
- [ ] Verify response formats match documentation
- [ ] Test error scenarios and confirm error messages
- [ ] Check that service ports are correct

#### Configuration Documentation (`configuration-reference.md`)
- [ ] Test environment variables with actual services
- [ ] Verify default values match code defaults
- [ ] Confirm YAML examples work with services
- [ ] Check that all options are documented

#### Testing Documentation (`testing-guide.md`)
- [ ] Run documented test commands and verify output
- [ ] Confirm test counts match actual test suite
- [ ] Verify test structure matches documentation
- [ ] Test memory testing procedures

#### Development Documentation (`development-guide.md`)
- [ ] Verify code examples compile and run
- [ ] Check that data models match actual implementations
- [ ] Confirm API patterns reflect current service structure
- [ ] Test validation and error handling examples

### 🔧 **Automated Validation Scripts**

Create these scripts to automate validation:

#### `scripts/validate_docs.sh`
```bash
#!/bin/bash
echo "Validating CLI documentation..."
# Test CLI commands from user-guide.md

echo "Validating API documentation..."
# Test API endpoints from api-documentation.md

echo "Validating test metrics..."
# Compare documented metrics with actual test results

echo "Documentation validation complete!"
```

#### `scripts/update_test_metrics.py`
```python
"""Update test metrics in documentation files"""
import subprocess
import re

def get_current_test_counts():
    # Run test commands and parse results
    pass

def update_docs_with_metrics(metrics):
    # Update testing-guide.md and deployment-guide.md
    pass
```

---

## Update Triggers & Workflows

### 🎯 **When to Update Each Document**

#### Immediate Updates (Same PR/Commit)
- **CLI changes** → Update `user-guide.md`
- **API changes** → Update `api-documentation.md`
- **Config changes** → Update `configuration-reference.md`
- **Architecture changes** → Update `development-guide.md`

#### Batch Updates (Weekly/Monthly)
- **Test metrics** → Update `testing-guide.md`, `deployment-guide.md`
- **Minor corrections** → Fix typos, improve clarity
- **Link validation** → Check internal/external links

#### Release Updates
- **Major version** → Review and update all documentation
- **Production metrics** → Update deployment guide with real stats
- **Feature completeness** → Ensure all features are documented

### 🔄 **Suggested Workflow**

#### For Feature Development:
1. **Code the feature** (new CLI command, API endpoint, etc.)
2. **Update relevant documentation** in same PR
3. **Validate documentation** using checklist
4. **Request documentation review** along with code review

#### For Maintenance:
1. **Weekly**: Run automated doc validation scripts
2. **Monthly**: Review and update test metrics
3. **Quarterly**: Full documentation review and cleanup

---

## Common Pitfalls & Solutions

### ❌ **Common Mistakes**

1. **Copy-paste errors**: Copying examples without testing them
   - **Solution**: Always run documented commands/API calls

2. **Stale metrics**: Test counts and performance numbers get outdated
   - **Solution**: Automate metric collection where possible

3. **Inconsistent formatting**: Different styles across documents
   - **Solution**: Use templates and enforce consistency

4. **Missing edge cases**: Only documenting happy path
   - **Solution**: Include error scenarios and edge cases

5. **Broken internal links**: Links between docs become invalid
   - **Solution**: Regular link validation

### ✅ **Quality Indicators**

**Good Documentation**:
- Every command example works when copy-pasted
- API examples return expected responses
- Configuration examples start services successfully
- Test commands produce documented results
- Error scenarios are covered

**Warning Signs**:
- Users reporting that documented commands don't work
- API integration issues due to wrong documentation
- Support requests about basic usage
- Documentation issues in bug reports

---

## Templates & Examples

### 📋 **PR Template for Documentation Updates**

```markdown
## Documentation Updates

**Reason for Update**: (CLI change, API change, new feature, etc.)

**Files Modified**:
- [ ] docs/user-guide.md - (describe changes)
- [ ] docs/api-documentation.md - (describe changes)
- [ ] docs/configuration-reference.md - (describe changes)
- [ ] docs/testing-guide.md - (describe changes)
- [ ] docs/deployment-guide.md - (describe changes)
- [ ] docs/development-guide.md - (describe changes)

**Validation Performed**:
- [ ] Tested all CLI commands in documentation
- [ ] Verified API examples work with actual services
- [ ] Confirmed configuration examples are functional
- [ ] Updated test metrics match current results
- [ ] Checked internal links are working
- [ ] Verified development examples compile and run

**Breaking Changes**: (Yes/No - describe if yes)

**Migration Notes**: (If users need to change their usage)
```

### 🎯 **Focus Areas for Each Document**

#### user-guide.md
- **Focus**: User experience and practical examples
- **Key sections**: CLI commands, common workflows, troubleshooting
- **Update triggers**: CLI changes, new features, user feedback

#### api-documentation.md
- **Focus**: Complete API reference for developers
- **Key sections**: Endpoints, data models, error codes
- **Update triggers**: API changes, new services, integration issues

#### testing-guide.md
- **Focus**: Testing procedures for contributors
- **Key sections**: Test commands, infrastructure, debugging
- **Update triggers**: Test structure changes, new testing tools

#### configuration-reference.md
- **Focus**: Complete configuration options for operations
- **Key sections**: Environment variables, service configs, defaults
- **Update triggers**: New config options, default changes, deployment issues

#### deployment-guide.md
- **Focus**: Production deployment and operations
- **Key sections**: Requirements, installation steps, monitoring
- **Update triggers**: Major releases, production experience, requirement changes

#### development-guide.md
- **Focus**: Technical implementation patterns and standards
- **Key sections**: Data models, service communication, development standards
- **Update triggers**: Architecture changes, new patterns, development process updates

---

## Success Metrics

### 📊 **How to Measure Documentation Quality**

**Quantitative Metrics**:
- Zero broken examples in documentation
- 100% of CLI commands work as documented
- All API examples return expected responses
- Configuration examples successfully start services
- Development examples compile and run correctly

**Qualitative Indicators**:
- Reduced support requests about basic usage
- Positive feedback about documentation accuracy
- New contributors can follow guides successfully
- Integration partners report smooth onboarding

**Monthly Review Questions**:
1. Are users able to complete common tasks using only the documentation?
2. Do the examples work without modification?
3. Are error messages and troubleshooting sections helpful?
4. Is the documentation finding and fixing issues before users encounter them?

---

## Quick Reference

### 🚀 **Common Update Commands**

```bash
# Validate all CLI examples work
scripts/validate_cli_docs.sh

# Update test metrics in docs
python scripts/update_test_metrics.py

# Check for broken links
scripts/check_doc_links.sh

# Validate API documentation
scripts/validate_api_docs.sh

# Test development guide examples
scripts/validate_dev_examples.sh
```

### 📝 **Before Every Release**

1. Run full documentation validation suite
2. Update all test metrics and performance numbers
3. Verify system requirements are current
4. Check that all new features are documented
5. Confirm examples work on clean environment

**Remember**: Great documentation is a force multiplier - it reduces support burden, improves user experience, and enables faster adoption. The investment in keeping it current pays dividends.
