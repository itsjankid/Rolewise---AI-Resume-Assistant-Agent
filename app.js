const sample = {
  role: "Frontend Developer Intern",
  job: "We are looking for a curious frontend developer intern to build responsive web experiences. You will collaborate with product designers and engineers, implement accessible interfaces using React, JavaScript, HTML, and CSS, connect REST APIs, write tests, and use Git in an agile team. Familiarity with TypeScript and performance optimization is a plus.",
  resume: `EDUCATION
B.S. Computer Science, Northfield University | Expected May 2027
Relevant coursework: Data Structures, Web Development, Human-Computer Interaction

PROJECTS
Campus Events | React, JavaScript, CSS
Built a responsive event discovery app for student organizations. Added category filtering and a reusable event card layout.

Study Group Finder | JavaScript, HTML, CSS
Created a study partner matching prototype and tested the sign-up flow with 8 classmates.

EXPERIENCE
Web Assistant, Northfield Student Union | Sep 2025 - Present
Updated event pages and checked content across mobile and desktop layouts. Worked with a designer to refine page navigation.

SKILLS
JavaScript, React, HTML, CSS, Git, Figma`
};

const $ = (selector) => document.querySelector(selector);
const roleInput = $("#role-input");
const jobInput = $("#job-input");
const resumeInput = $("#resume-input");
const formError = $("#form-error");
let latestReport = null;

function escapeHTML(value) {
  if (value == null) return "";
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character]);
}

function renderTerms(container, terms, isMissing) {
  if (!terms || !terms.length) {
    container.innerHTML = `<span class="term-empty">${isMissing ? "No gaps flagged from the current role signals." : "No direct matches detected yet."}</span>`;
    return;
  }

  container.innerHTML = terms
    .map((term) => `<span class="term-chip${isMissing ? " missing" : ""}">${escapeHTML(term)}</span>`)
    .join("");
}

function renderReport(report) {
  $("#empty-state").hidden = true;
  $("#results-content").hidden = false;
  $("#review-date").textContent = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(new Date()).toUpperCase();

  const score = Number(report.score || 0);
  $("#score-value").textContent = score;
  $("#score-gauge").style.setProperty("--score-angle", `${score}%`);

  const verdict = score >= 75 ? "Strong role fit" : score >= 45 ? "Good overlap" : "Needs more role alignment";
  $("#score-verdict").textContent = verdict;
  $("#score-description").textContent = report.matchSummary || `For ${report.role}, based on available role signals.`;
  $("#term-count").textContent = `${(report.found || []).length} of ${(report.keywords || []).length} signals found`;
  $("#found-count").textContent = `${(report.found || []).length} FOUND`;
  $("#missing-count").textContent = `${(report.missing || []).length} TO CHECK`;

  renderTerms($("#found-terms"), report.found || [], false);
  renderTerms($("#missing-terms"), report.missing || [], true);

  const recommendations = report.recommendations && report.recommendations.length
    ? report.recommendations
    : ["Add role-specific keywords to your Skills or Projects section.", "Turn one bullet into a result-driven experience statement."];

  $("#recommendation-list").innerHTML = recommendations
    .map((item, index) => `<li><strong>Focus ${index + 1}.</strong> ${escapeHTML(item)}</li>`)
    .join("");
}

async function analyze() {
  const role = roleInput.value.trim();
  const resume = resumeInput.value.trim();
  if (!role || !resume) {
    formError.textContent = !role && !resume ? "Add a target role and your resume to start the review." : !role ? "Add a target role so the review knows what to look for." : "Paste your resume text or import a .txt file to continue.";
    formError.hidden = false;
    (!role ? roleInput : resumeInput).focus();
    return;
  }

  formError.hidden = true;
  $("#analyze-button").disabled = true;
  $("#analyze-button").textContent = "Reviewing...";

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        role,
        jobDescription: jobInput.value.trim(),
        resume
      })
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "The analysis failed.");
    }

    latestReport = data;
    renderReport(data);
  } catch (error) {
    formError.textContent = error.message || "Something went wrong while reviewing the resume.";
    formError.hidden = false;
  } finally {
    $("#analyze-button").disabled = false;
    $("#analyze-button").innerHTML = '<span>Review my match</span><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h11m-4-4 4 4-4 4" /></svg>';
  }
}

function loadSample() {
  roleInput.value = sample.role;
  jobInput.value = sample.job;
  resumeInput.value = sample.resume;
  updateCharacterCount();
  formError.hidden = true;
  roleInput.focus();
}

function updateCharacterCount() {
  const count = resumeInput.value.length;
  $("#character-count").textContent = `${count.toLocaleString()} character${count === 1 ? "" : "s"}`;
}

function downloadReport() {
  if (!latestReport) return;

  const text = [
    `ROLEWISE RESUME REVIEW: ${latestReport.role}`,
    `Model/provider: ${latestReport.model || "local"}`,
    `Match score: ${latestReport.score}%`,
    ``,
    `Found: ${(latestReport.found || []).join(", ") || "None"}`,
    `Worth checking: ${(latestReport.missing || []).join(", ") || "None"}`,
    ``,
    "Recommendations:",
    ...((latestReport.recommendations || []).map((item, index) => `${index + 1}. ${item}`)),
    "",
    "This review is grounded in the resume content and role keywords, and does not invent experience."
  ].join("\n");

  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "resume-fit-review.txt";
  link.click();
  URL.revokeObjectURL(url);
}

$("#sample-button").addEventListener("click", loadSample);
$("#analyze-button").addEventListener("click", analyze);
$("#download-button").addEventListener("click", downloadReport);
$("#edit-button").addEventListener("click", () => roleInput.focus());
resumeInput.addEventListener("input", updateCharacterCount);

for (const input of [roleInput, jobInput, resumeInput]) {
  input.addEventListener("input", () => {
    if (!formError.hidden) formError.hidden = true;
  });
}

$("#file-input").addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;

  resumeInput.value = await file.text();
  updateCharacterCount();
  formError.hidden = true;
  event.target.value = "";
});

updateCharacterCount();