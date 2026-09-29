#!/usr/bin/env python3
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from urllib import request, error

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8000"))
CONFIG_PATH = os.path.join(ROOT, "config.json")


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


load_env_file(os.path.join(ROOT, ".env"))


def read_runtime_config():
    config = {
        "provider": os.environ.get("AI_PROVIDER", "local").lower(),
        "model": os.environ.get("OPENAI_MODEL") or os.environ.get("GEMINI_MODEL") or "",
        "apiKey": os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY") or "",
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            for key in ("provider", "model", "apiKey"):
                if loaded.get(key):
                    config[key] = loaded[key]
        except Exception:
            pass

    if config["provider"] not in {"openai", "gemini", "local"}:
        config["provider"] = "local"

    if config["provider"] == "openai":
        config["apiKey"] = config["apiKey"] or os.environ.get("OPENAI_API_KEY", "")
        config["model"] = config["model"] or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    elif config["provider"] == "gemini":
        config["apiKey"] = config["apiKey"] or os.environ.get("GEMINI_API_KEY", "")
        config["model"] = config["model"] or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    else:
        config["model"] = config["model"] or ""
        config["apiKey"] = ""

    return config


def save_runtime_config(provider, model, api_key):
    cleaned = {"provider": provider or "local", "model": model or "", "apiKey": api_key or ""}
    with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
        json.dump(cleaned, handle, indent=2)
    os.environ["AI_PROVIDER"] = cleaned["provider"]
    if cleaned["provider"] == "openai":
        os.environ["OPENAI_API_KEY"] = cleaned["apiKey"]
        os.environ["OPENAI_MODEL"] = cleaned["model"] or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    elif cleaned["provider"] == "gemini":
        os.environ["GEMINI_API_KEY"] = cleaned["apiKey"]
        os.environ["GEMINI_MODEL"] = cleaned["model"] or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    return cleaned


def normalize_space(value):
    return " ".join(str(value).split())


def keywords_for_role(role_text, job_text):
    text = f"{role_text} {job_text}".lower()
    groups = {
        "Frontend development": [
            "react", "javascript", "typescript", "html", "css", "responsive design",
            "accessibility", "web performance", "rest api", "rest apis", "testing",
            "git", "ui", "frontend", "front-end", "next.js", "vue", "design systems",
            "user experience", "accessibility", "agile"
        ],
        "Software engineering": [
            "python", "java", "c++", "data structures", "algorithms", "sql",
            "debugging", "linux", "cloud", "docker", "testing", "git", "typescript",
            "agile", "system design", "oop", "rest api", "microservices"
        ],
        "Data analysis": [
            "python", "sql", "excel", "tableau", "power bi", "data visualization",
            "statistics", "machine learning", "pandas", "analytics", "a/b testing",
            "dashboard", "etl", "r"
        ],
        "Product management": [
            "product strategy", "user research", "roadmap", "product analytics",
            "a/b testing", "stakeholder", "market research", "prioritization",
            "agile", "wireframes", "requirements", "metrics"
        ],
        "UX / Product design": [
            "figma", "prototyping", "user research", "usability testing", "wireframes",
            "accessibility", "design systems", "interaction design", "information architecture",
            "visual design", "user flows", "product thinking"
        ],
        "Marketing": [
            "content strategy", "seo", "social media", "campaign", "analytics",
            "copywriting", "email marketing", "market research", "google analytics",
            "brand", "engagement", "conversion"
        ],
        "Business / Consulting": [
            "excel", "powerpoint", "sql", "data analysis", "research", "stakeholder",
            "presentation", "financial modeling", "strategy", "communication",
            "problem solving", "process improvement"
        ],
    }

    patterns = [
        (re.compile(r"(frontend|front-end|web developer|ui engineer|ui/ux)", re.I), "Frontend development"),
        (re.compile(r"(software|back-end|backend|full.stack|developer|engineering)", re.I), "Software engineering"),
        (re.compile(r"(data analyst|data science|business intelligence|analytics)", re.I), "Data analysis"),
        (re.compile(r"(product manager|product management|product intern)", re.I), "Product management"),
        (re.compile(r"(ux|ui/ux|product design|designer)", re.I), "UX / Product design"),
        (re.compile(r"(marketing|growth|communications)", re.I), "Marketing"),
        (re.compile(r"(consult|business analyst|finance|operations)", re.I), "Business / Consulting"),
    ]

    detected_group = None
    for pattern, group_name in patterns:
        if pattern.search(role_text):
            detected_group = group_name
            break

    base_keywords = groups.get(detected_group, [
        "communication", "teamwork", "research", "problem solving", "project management",
        "leadership", "data analysis", "presentation", "time management", "writing"
    ])

    found_keywords = []
    for keyword in base_keywords:
        escaped = re.escape(keyword)
        if re.search(rf"(^|[^a-z0-9]){escaped}([^a-z0-9]|$)", text, flags=re.I):
            found_keywords.append(keyword)

    if len(found_keywords) == 0:
        return base_keywords[:8]

    return list(dict.fromkeys(found_keywords))[:12]


def local_review(role, job_description, resume):
    keywords = keywords_for_role(role, job_description)
    text = resume.lower()
    found = []
    for keyword in keywords:
        pattern = re.compile(rf"(^|[^a-z0-9]){re.escape(keyword)}([^a-z0-9]|$)", re.I)
        if pattern.search(text):
            found.append(keyword)
    missing = [keyword for keyword in keywords if keyword not in found]
    score = round((len(found) / max(len(keywords), 1)) * 100)

    recommendations = []
    if missing:
        recommendations.append(f"Add the most relevant missing keywords to your Skills or Projects section: {', '.join(missing[:3])}.")
    else:
        recommendations.append("Tighten your strongest role-fit evidence by turning one resume bullet into a result-driven impact statement.")

    if not re.search(r"\b(increased|improved|reduced|saved|grew|raised|cut|automated|launched|delivered|supported|built|developed)\b", resume, flags=re.I):
        recommendations.append("Include one result-focused bullet that shows the scope, action, and measurable outcome of your work.")
    else:
        recommendations.append("Make sure your strongest bullets clearly state the problem, your action, and the outcome.")

    if not re.search(r"\b(projects|experience|skills|education)\b", resume, flags=re.I):
        recommendations.append("Add clear resume headings like Education, Skills, Experience, and Projects so the role fit is easier to scan.")
    else:
        recommendations.append("Move your most relevant project or experience earlier in the resume if it matches the target role.")

    return {
        "role": role,
        "jobDescription": job_description,
        "score": max(0, min(100, score)),
        "keywords": keywords,
        "found": found,
        "missing": missing,
        "recommendations": recommendations[:4],
        "matchSummary": "This resume shows partial alignment with the target role, with the strongest overlap in the skills and project areas most directly connected to the role.",
        "strengths": found[:5] if found else ["Relevant coursework", "Project work", "Hands-on experience"],
        "gaps": missing[:5] if missing else ["No major gaps flagged based on the current review."],
        "rewrittenExamples": [
            {
                "before": "Built a responsive event app for student organizations.",
                "after": "Built a responsive event discovery app with category filtering and reusable UI components, improving navigation and discoverability for student organization events."
            }
        ],
        "nextSteps": [
            "Add any missing role-specific tools or technologies to the Skills section.",
            "Turn one project bullet into a result-driven example with a concrete outcome.",
            "Reorder your strongest matching project or internship experience near the top."
        ],
        "model": "local heuristic engine"
    }


def call_openai(prompt):
    config = read_runtime_config()
    api_key = config["apiKey"] or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI key missing")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = config["model"] or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "You are a resume-fit reviewer for early-career students. Prefer evidence-based resume feedback and never invent experience."},
            {"role": "user", "content": prompt},
        ],
    }
    req = request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        response_data = json.loads(response.read().decode("utf-8"))
    body = response_data["choices"][0]["message"]["content"]
    return body


def call_gemini(prompt):
    config = read_runtime_config()
    api_key = config["apiKey"] or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Gemini key missing")

    model = config["model"] or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        response_data = json.loads(response.read().decode("utf-8"))
    return response_data["candidates"][0]["content"]["parts"][0]["text"]


def extract_json_from_text(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start : end + 1])
    return None


def ai_review(role, job_description, resume):
    config = read_runtime_config()
    provider = config["provider"].lower()
    prompt = f"""
You are evaluating a student's resume for a target role.
Return JSON only with this exact structure:
{
  "score": 0,
  "matchSummary": "string",
  "strengths": ["item1", "item2"],
  "gaps": ["item1", "item2"],
  "found": ["item1", "item2"],
  "missing": ["item1", "item2"],
  "recommendations": ["item1", "item2", "item3"],
  "rewrittenExamples": [{"before": "string", "after": "string"}],
  "nextSteps": ["item1", "item2", "item3"],
  "keywords": ["item1", "item2"]
}

Target role: {role}
Job description: {job_description}
Resume:
{resume}

Rules:
- Do NOT invent experience or metrics.
- Keep the response realistic for an internship or entry-level role.
- Score should be between 0 and 100.
- found and missing should be skill/keyword lists aligned to the role.
- recommendations should be concrete and role-specific.
"""

    try:
        if provider == "openai":
            body = call_openai(prompt)
        elif provider == "gemini":
            body = call_gemini(prompt)
        else:
            raise RuntimeError("No AI provider configured")
    except Exception:
        return local_review(role, job_description, resume)

    parsed = extract_json_from_text(body)
    if not parsed:
        return local_review(role, job_description, resume)

    transformed = {
        "role": role,
        "jobDescription": job_description,
        "score": int(parsed.get("score", 0)),
        "keywords": parsed.get("keywords") or [],
        "found": parsed.get("found") or [],
        "missing": parsed.get("missing") or [],
        "recommendations": parsed.get("recommendations") or [],
        "matchSummary": parsed.get("matchSummary") or "Resume fit review generated by the AI model.",
        "strengths": parsed.get("strengths") or [],
        "gaps": parsed.get("gaps") or [],
        "rewrittenExamples": parsed.get("rewrittenExamples") or [],
        "nextSteps": parsed.get("nextSteps") or [],
        "model": provider,
    }
    if transformed["score"] < 0:
        transformed["score"] = 0
    if transformed["score"] > 100:
        transformed["score"] = 100
    return transformed


class ResumeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/health":
            config = read_runtime_config()
            provider = config["provider"].lower()
            self.send_json({
                "status": "ok",
                "provider": provider if provider in {"openai", "gemini"} else "local",
                "model": config["model"],
                "message": "Resume Fit Assistant is running with an AI provider." if provider in {"openai", "gemini"} else "Local heuristic mode is active.",
            })
            return

        if url.path == "/api/config":
            config = read_runtime_config()
            self.send_json({
                "provider": config["provider"],
                "model": config["model"],
                "apiKeyConfigured": bool(config["apiKey"])
            })
            return

        safe_path = url.path.strip("/") or "index.html"
        file_path = os.path.join(ROOT, safe_path)

        if not os.path.exists(file_path) or os.path.isdir(file_path):
            file_path = os.path.join(ROOT, "index.html")

        if not file_path.startswith(ROOT):
            self.send_error(403)
            return

        content_type = "text/html; charset=utf-8"
        if file_path.endswith(".css"):
            content_type = "text/css; charset=utf-8"
        elif file_path.endswith(".js"):
            content_type = "application/javascript; charset=utf-8"
        elif file_path.endswith(".json"):
            content_type = "application/json; charset=utf-8"

        try:
            with open(file_path, "rb") as handle:
                data = handle.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_error(404)

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/api/config":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self.send_json({"error": "Invalid JSON payload."}, status=400)
                return

            provider = str(payload.get("provider", "local")).lower()
            model = str(payload.get("model", "")).strip()
            api_key = str(payload.get("apiKey", "")).strip()
            if provider not in {"local", "openai", "gemini"}:
                provider = "local"

            if provider == "local":
                model = ""
                api_key = ""

            save_runtime_config(provider, model, api_key)
            self.send_json({
                "message": "AI settings saved successfully." if provider != "local" else "Switched back to local heuristic mode.",
                "provider": provider,
                "model": model,
                "apiKeyConfigured": bool(api_key)
            })
            return

        if url.path != "/api/analyze":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self.send_json({"error": "Invalid JSON payload."}, status=400)
            return

        role = normalize_space(payload.get("role", ""))
        job_description = normalize_space(payload.get("jobDescription", ""))
        resume = normalize_space(payload.get("resume", ""))

        if not role or not resume:
            self.send_json({"error": "Role and resume text are required."}, status=400)
            return

        config = read_runtime_config()
        provider = config["provider"].lower()
        if provider in {"openai", "gemini"}:
            result = ai_review(role, job_description, resume)
            self.send_json({**result, "provider": provider})
        else:
            result = local_review(role, job_description, resume)
            self.send_json({**result, "provider": "local"})

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    try:
        server = ThreadingHTTPServer(("0.0.0.0", PORT), ResumeHandler)
        print(f"Resume Fit Assistant running on http://localhost:{PORT}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
