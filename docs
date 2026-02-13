# GeoFix Project Planning Prompt

You are an expert software architect specializing in geospatial systems and AI integration. Your task is to design a complete project plan for **GeoFix** - an autonomous geospatial data correction system with conversational AI interface.

## PHASE 1: DEEP PROJECT ANALYSIS (Required First Step)

Before planning anything, you MUST thoroughly analyze these two existing projects:

### 1. Review OVC (Overlap Violation Checker)
**Project README provided above**

Analyze and document:
- What quality checks does OVC perform? (List all checks)
- What are the input/output formats?
- How is the architecture structured? (folders, modules, key files)
- What geometry operations does it use?
- What are the performance characteristics?
- What validation workflows exist?
- How does the pipeline work? (loaders → checks → metrics → export)
- What external dependencies does it use?

### 2. Review GeoQA
**Project README provided above**

Analyze and document:
- What is GeoQA's role in the ecosystem?
- How does it integrate with OVC?
- What quality metrics does it compute?
- What validation checks does it perform?
- What is its profiling capability?
- How does the scoring system work?

### 3. Understand the Integration
- How do OVC and GeoQA work together?
- What is the data flow between them?
- What quality gates exist?
- What outputs are generated?

## PHASE 2: GEOFIX REQUIREMENTS

Based on your analysis, design **GeoFix** with these capabilities:

### Core Functionality
1. **Autonomous Data Correction**
   - Detect errors using OVC/GeoQA
   - Analyze context (source accuracy, date, confidence)
   - Make intelligent fix decisions
   - Execute geometry corrections
   - Validate fixes don't create new errors
   - Generate audit trail with explanations

2. **Semantic Topology Correction**
   - Use metadata to inform decisions (not just geometry)
   - Apply hierarchical decision logic:
     * Tier 1: Rule-based (deterministic, fast)
     * Tier 2: LLM reasoning (ambiguous cases)
     * Tier 3: Human-in-loop (low confidence)
   - Example: "Building overlaps road" → Check accuracies → Snap lower accuracy to higher

3. **Conversational Interface**
   - Upload geospatial files (Shapefile, GeoJSON, GeoPackage)
   - Natural language queries: "What errors exist in my data?"
   - Interactive fixing: "Fix all overlaps automatically"
   - Selective fixing: "Show me buildings that need review"
   - Explain decisions: "Why did you snap building #42?"

### Integration Requirements
- Leverage existing OVC error detection (don't rebuild)
- Use GeoQA for pre-flight data quality checks
- Extend OVC's pipeline architecture
- Maintain compatibility with OVC's output formats

## PHASE 3: TECHNICAL DESIGN

### 3.1 System Architecture
Design the complete system architecture including:
- Component diagram showing GeoFix, OVC, GeoQA relationships
- Data flow diagram (from input files → fixes → outputs)
- Decision engine architecture (rules + LLM + human review)
- Metadata management system

### 3.2 Technology Stack
Recommend and justify:
- LLM framework (LangChain, LlamaIndex, or custom?)
- Which LLM model(s) to use (Claude, GPT-4, etc.)
- UI framework (Streamlit, Gradio, Chainlit, custom?)
- Database for audit logs (SQLite, PostgreSQL?)
- Any new dependencies needed

### 3.3 Project Structure
Design complete folder/file structure:
```
geofix/
├── core/           # What goes here?
├── decision/       # What goes here?
├── fixes/          # What goes here?
├── metadata/       # What goes here?
├── chat/           # What goes here?
├── integration/    # How to integrate OVC/GeoQA?
└── ...
```

Specify:
- All major directories and their purpose
- Key Python modules and what they contain
- Where OVC/GeoQA integration happens
- Configuration file locations

### 3.4 Core Modules Design

For each major module, specify:
- **File name and location**
- **Classes and their responsibilities**
- **Key functions and their signatures**
- **Dependencies on OVC/GeoQA**

Critical modules to design:
1. **Metadata System** - How to store/manage source, accuracy, confidence
2. **Decision Engine** - Rule evaluation + LLM orchestration
3. **Fix Operations** - Geometry correction implementations
4. **Validation System** - Ensure fixes don't create new problems
5. **Audit Logger** - Track what changed, why, confidence
6. **Chat Interface** - LLM conversation + tool calling
7. **OVC Integration** - Use existing error detection
8. **GeoQA Integration** - Pre-flight quality checks

### 3.5 Data Models
Define key data structures:
- `FeatureMetadata` - What fields? How stored?
- `DetectedError` - How to extend OVC's error format?
- `FixStrategy` - What information needed?
- `FixResult` - What to track?
- `AuditEntry` - What to log?

### 3.6 Fix Operations Library
Design the geometry correction operations:
- List all fix types (snap, trim, merge, split, buffer, etc.)
- For each fix, specify:
  * When to apply
  * Input parameters
  * Shapely operations used
  * Validation requirements
  * Confidence scoring

### 3.7 Decision Rules
Design the rule-based system:
- List 10-15 deterministic rules for common cases
- Format: IF (conditions) THEN (fix_strategy) CONFIDENCE (score)
- Example: "IF overlap_ratio > 0.95 AND same_source THEN merge CONFIDENCE 0.95"

### 3.8 LLM Integration
Design the LLM reasoning system:
- What information to pass in prompts?
- What tools/functions to expose?
- How to parse LLM responses?
- How to score confidence?
- Fallback strategies if LLM fails?

### 3.9 User Interface Design
Design the chat interface:
- What conversational flows to support?
- How to handle file uploads?
- How to display results (maps, tables, reports)?
- How to handle human review workflow?
- What visualizations to show?

## PHASE 4: IMPLEMENTATION ROADMAP

### 4.1 Development Phases
Break down into phases with:
- Timeline (weeks)
- Deliverables
- Dependencies
- Testing requirements

Suggested phases:
- Phase 1: Foundation & OVC integration
- Phase 2: Metadata & decision engine
- Phase 3: Fix operations
- Phase 4: LLM integration
- Phase 5: Chat interface
- Phase 6: Validation & testing
- Phase 7: Polish & documentation

### 4.2 MVP Definition
What is the Minimum Viable Product?
- Which features MUST be in v1.0?
- Which can wait for v1.1, v1.2?
- What demonstrates the core value proposition?

### 4.3 Testing Strategy
- Unit tests for fix operations
- Integration tests with OVC/GeoQA
- Geometry validation tests
- LLM response handling tests
- End-to-end workflow tests

## PHASE 5: DELIVERABLES

Provide the following deliverables:

### 1. Executive Summary
- 2-page overview of GeoFix
- Problem statement
- Solution approach
- Key innovations
- Expected impact

### 2. Complete Technical Specification
- All sections from Phase 3 (architecture, stack, modules, data models)
- Detailed enough that a developer can start coding immediately

### 3. File-by-File Implementation Guide
For the MVP, list every file that needs to be created:
```
geofix/core/config.py
  Purpose: ...
  Key classes: ...
  Integration points: ...
  Implementation notes: ...
```

### 4. Code Scaffolding
Provide skeleton code for critical modules:
- Decision engine entry point
- LLM tool calling setup
- Fix operation base class
- Metadata schema

### 5. Development Roadmap
Week-by-week plan for building GeoFix MVP (aim for 6-8 weeks)

### 6. Integration Guide
How to integrate with existing OVC/GeoQA:
- Import strategies
- Code reuse opportunities  
- Extension points
- Backwards compatibility

### 7. Dependencies & Setup
- Complete requirements.txt
- Installation instructions
- Development environment setup
- API keys needed (Anthropic, etc.)

## OUTPUT FORMAT

Structure your response as:

# GeoFix: Complete Project Plan

## Part 1: Project Analysis
[Your analysis of OVC and GeoQA]

## Part 2: System Design
[Architecture, tech stack, data models]

## Part 3: Implementation Specification
[Detailed module designs, file structure]

## Part 4: Development Roadmap
[Phase-by-phase plan with timelines]

## Part 5: Code Scaffolding
[Skeleton code for key components]

## Part 6: Next Steps
[Immediate actions to start development]

---

## CONSTRAINTS & PRIORITIES

- **Reuse over rebuild**: Leverage OVC/GeoQA extensively
- **Practical over perfect**: Focus on solving real problems
- **Incremental delivery**: Each phase should produce working software
- **Clear value**: Each feature should have obvious utility
- **Maintainable**: Clean architecture, well-documented
- **Cost-conscious**: Optimize LLM usage to keep costs reasonable

## QUESTIONS TO ADDRESS

As you design, explicitly answer:
1. How does GeoFix extend vs replace OVC functionality?
2. Where exactly does the LLM add value vs rule-based logic?
3. How to handle cases where automatic fixing could be risky?
4. What metadata is realistic to expect from users?
5. How to make the system learn from corrections over time?
6. What's the migration path from manual OVC usage to automated GeoFix?

---

Begin your analysis now. Be thorough, specific, and actionable.