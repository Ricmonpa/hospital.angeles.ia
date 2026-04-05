Project Name: OpenDoc (OpenClaw Verticalization for Mexican Doctors)
1. Executive Summary
OpenDoc is an autonomous AI agent architecture based on OpenClaw, specifically "tropicalized" and verticalized for the Mexican medical market. It operates as a private, secure, and proactive administrator for doctors, running on a dedicated Linux VPS per client to ensure data sovereignty and strict privacy compliance.

Core Value Proposition: OpenDoc automates the administrative burden of medical practice in Mexico: SAT taxation, COFEPRIS regulatory compliance, patient scheduling, and clinical documentation. It leverages Google's Gemini 1.5 models for high-fidelity multimodal understanding and massive context reasoning.

2. Tech Stack & Infrastructure
Base Framework: OpenClaw (Python-based agent orchestration).

LLM Engine:

Gemini 1.5 Pro: For complex reasoning, legal analysis (LISR/NOMs), and medical context.

Gemini 1.5 Flash: For high-speed, low-latency chat, routing, and simple extraction tasks.

API Provider: Google AI Studio / Vertex AI.

Deployment: Docker containers running on Linux VPS (Ubuntu/Debian via Hetzner/DigitalOcean).

Database: PostgreSQL (structured data) + Vector DB (semantic search for medical guidelines).

Browser Automation: Playwright (headless) controlled by the agent for SAT and Insurance portals.

Interface: WhatsApp Business API + Minimalist Web Dashboard (React/Next.js).

3. Core Agent Skills (The "OpenDoc Toolbelt")
The agent uses Gemini Function Calling to execute these Python-based tools:

A. The "Fiscalista" (Tax Accountant)
Tool: sat_portal_navigator

Action: Log in to sat.gob.mx using CIEC/e.firma credentials (securely stored locally).

Action: Scrape/Download XML invoices (Received/Issued).

Logic: Use Gemini 1.5 Pro to classify expenses strictly based on LISR (Ley del Impuesto Sobre la Renta) rules for medical deductions.

Tool: receipt_vision_analyzer

Action: Process images of physical receipts uploaded via WhatsApp. Gemini Vision extracts date, amount, RFC, and concept directly from the image with high accuracy.

B. The "Clinical Assistant"
Tool: prescription_generator

Action: Generate a valid PDF prescription complying with COFEPRIS guidelines (University, Cedula, Address).

Tool: patient_history_context

Action: Analyze patient history. Gemini's 1M+ token context allows injecting entire past medical records into the prompt for accurate summarization without losing detail.

C. The "Bureaucrat" (Regulatory Watchdog)
Tool: watchdog_service

Action: Monitor expiration dates for e.firma, CSD (Sellos Digitales), and Board Certifications.

Action: Proactive alerts via WhatsApp 90/60/30 days before expiration.

4. Architecture Guidelines (Strict Rules)
Privacy First: Patient PII (Personally Identifiable Information) stays in the VPS database. Only anonymized context is sent to the LLM.

No Hallucinations on Health: If unsure about a medical query, OpenDoc must flag it for human review. It does NOT diagnose; it assists administratively.

Authentication Handling: Browser sessions must handle 2FA/CAPTCHAs by requesting user intervention via WhatsApp if automation fails.

Cost Optimization: Default to Gemini 1.5 Flash for all routine routing and simple Q&A to keep operating costs minimal.

5. Development Roadmap (MVP)
Phase 1 (The Setup): Dockerize OpenClaw environment on Linux. Configure google-generativeai Python SDK.

Phase 2 (The Persona): Create SOUL.md defining the "OpenDoc" persona (Efficient, compliant, protective of the doctor's license).

Phase 3 (The Vision): Implement receipt_vision_analyzer using Gemini Vision to test multimodal capabilities on Mexican invoices.

Phase 4 (The Action): Implement sat_portal_navigator (Browser Use) for basic tax compliance.