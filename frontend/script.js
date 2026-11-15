const query = document.getElementById("submit");

(() => {
    "use strict";

    const form = document.querySelector("form");
    const output = document.getElementById("output");
    if (!form || !output) return;

    const studentId = document.getElementById("sid");
    const minUnits = document.getElementById("min_unit_load");
    const maxUnits = document.getElementById("max_unit_load");
    const submitButton = form.querySelector('button[type="submit"]');

    const MAX_UNITS = 30;
    const STORAGE_KEY = "graduationPlanner.form";
    // The student ID is not remembered, so it is never left behind on a shared computer.
    const REMEMBERED_FIELDS = ["schools", "major", "min_unit_load", "max_unit_load"];

    let isSubmitting = false;

    // Message area, created here so index.html does not need to change.
    const message = document.createElement("p");
    message.id = "form-message";
    message.setAttribute("aria-live", "polite");
    form.insertAdjacentElement("afterend", message);

    function showMessage(text, isError) {
        message.textContent = text;
        message.className = isError ? "error-message" : "status-message";
    }

    function clearErrors() {
        form.querySelectorAll("[aria-invalid]").forEach((field) => field.removeAttribute("aria-invalid"));
        if (message.className === "error-message") showMessage("", false);
    }

    // Blank is allowed (the planner uses the student's saved unit range).
    function readUnits(input, label) {
        const text = input.value.trim();
        // A number box holding unreadable text reports an empty value but a bad-input flag.
        if (input.validity && input.validity.badInput) {
            return { input, text: `${label} must be a whole number from 0 to ${MAX_UNITS}.` };
        }
        if (text === "") return { value: null };
        if (!/^\d+$/.test(text) || Number(text) > MAX_UNITS) {
            return { input, text: `${label} must be a whole number from 0 to ${MAX_UNITS}.` };
        }
        return { value: Number(text) };
    }

    function validate() {
        const problems = [];

        if (studentId.value.trim() === "") {
            problems.push({ input: studentId, text: "Enter your student ID." });
        }

        const min = readUnits(minUnits, "Minimum units");
        const max = readUnits(maxUnits, "Maximum units");
        if (min.text) problems.push(min);
        if (max.text) problems.push(max);
        if (min.value != null && max.value != null && min.value > max.value) {
            problems.push({ input: minUnits, text: "Minimum units cannot be greater than maximum units." });
        }

        return problems;
    }

    function showProblems(problems) {
        problems.forEach((problem) => problem.input.setAttribute("aria-invalid", "true"));
        showMessage(problems.map((problem) => problem.text).join(" "), true);
        problems[0].input.focus();
    }

    function saveForm() {
        try {
            const data = {};
            REMEMBERED_FIELDS.forEach((id) => {
                data[id] = document.getElementById(id).value;
            });
            localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        } catch (error) {
            // Storage can be blocked by the browser; the form still works without it.
        }
    }

    function restoreForm() {
        try {
            const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
            REMEMBERED_FIELDS.forEach((id) => {
                const field = document.getElementById(id);
                if (!field || typeof data[id] !== "string") return;
                const isSelect = field.tagName === "SELECT";
                if (isSelect && ![...field.options].some((o) => o.value === data[id] && !o.disabled)) return;
                field.value = data[id];
            });
        } catch (error) {
            // Ignore unreadable saved data.
        }
    }

    // Where a structured plan is drawn. Created here so index.html does not need to change.
    const planBox = document.createElement("div");
    planBox.id = "plan";
    output.insertAdjacentElement("afterend", planBox);

    // Builds elements with textContent only, so text from the planner is never read as HTML.
    function el(tag, text, className) {
        const node = document.createElement(tag);
        if (text !== undefined) node.textContent = text;
        if (className) node.className = className;
        return node;
    }

    function renderList(title, items) {
        if (!Array.isArray(items) || items.length === 0) return null;
        const section = el("section");
        section.appendChild(el("h2", title));
        const list = el("ul");
        items.forEach((item) => list.appendChild(el("li", String(item))));
        section.appendChild(list);
        return section;
    }

    function renderCourses(courses) {
        const table = el("table");
        const head = el("tr");
        ["Course", "Name", "Units", "Why it is in the plan"].forEach((title) => head.appendChild(el("th", title)));
        table.appendChild(el("thead")).appendChild(head);

        const body = el("tbody");
        courses.forEach((course) => {
            const row = el("tr");
            [course.code, course.name, course.credit_hours, course.reason].forEach((value) => {
                row.appendChild(el("td", value == null ? "" : String(value)));
            });
            body.appendChild(row);
        });
        table.appendChild(body);
        return table;
    }

    // Accepts the plan itself, or {plan: {...}, validation: {...}}. Returns null if it is not a plan.
    function renderPlan(data) {
        const plan = data.plan && typeof data.plan === "object" ? data.plan : data;
        if (!plan || !Array.isArray(plan.courses)) return null;
        const validation = data.validation || data.report || null;

        const box = el("div");
        box.appendChild(el("h2", "Your plan"));

        const totalUnits = plan.courses.reduce((sum, course) => sum + (Number(course.credit_hours) || 0), 0);
        box.appendChild(el("p", `${plan.courses.length} courses, ${totalUnits} units`, "plan-summary"));
        if (plan.courses.length > 0) box.appendChild(renderCourses(plan.courses));

        [renderList("Assumptions", plan.assumptions),
         renderList("Still to confirm", plan.unresolved_questions)].forEach((section) => {
            if (section) box.appendChild(section);
        });

        if (validation && typeof validation === "object") {
            const passed = validation.passed === true;
            box.appendChild(el("h2", passed ? "Validation: passed" : "Validation: review needed",
                passed ? "validation-pass" : "validation-review"));
            [renderList("Issues", validation.issues), renderList("Notes", validation.limitations)].forEach((section) => {
                if (section) box.appendChild(section);
            });
        }
        return box;
    }

    function clearResult() {
        output.textContent = "";
        planBox.textContent = "";
    }

    // A plan is drawn as a table; anything else is shown as plain text.
    function showResult(text) {
        clearResult();
        let data = null;
        try {
            data = JSON.parse(text);
        } catch (error) {
            data = null;
        }
        const drawn = data && typeof data === "object" ? renderPlan(data) : null;
        if (drawn) {
            planBox.appendChild(drawn);
        } else {
            output.textContent = text;
        }
    }

    async function submitForm() {
        isSubmitting = true;
        const originalLabel = submitButton ? submitButton.textContent : "";
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "Planning...";
        }
        clearResult();
        showMessage("Planning... this can take a few minutes.", false);

        try {
            const response = await fetch(form.getAttribute("action") || "", {
                method: "POST",
                body: new URLSearchParams(new FormData(form)),
            });
            if (!response.ok) {
                throw new Error(
                    `The planner returned an error (HTTP ${response.status}). The backend may not be connected yet.`
                );
            }
            showResult(await response.text());
            showMessage("", false);
        } catch (error) {
            const text = error instanceof TypeError
                ? "Could not reach the planner. Check that the server is running."
                : error.message;
            showMessage(text, true);
        } finally {
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = originalLabel;
            }
            isSubmitting = false;
        }
    }

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        if (isSubmitting) return;

        clearErrors();
        const problems = validate();
        if (problems.length > 0) {
            showProblems(problems);
            return;
        }

        saveForm();
        submitForm();
    });

    form.addEventListener("input", clearErrors);

    restoreForm();
})();
