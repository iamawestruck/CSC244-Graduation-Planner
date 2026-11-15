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

    async function submitForm() {
        isSubmitting = true;
        const originalLabel = submitButton ? submitButton.textContent : "";
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "Planning...";
        }
        output.textContent = "";
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
            output.textContent = await response.text(); // textContent: never interpreted as HTML
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
