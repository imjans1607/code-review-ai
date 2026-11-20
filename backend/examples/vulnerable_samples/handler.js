// Intentionally insecure examples, used to demonstrate the security scanner.

function render(userInput) {
  // Writing untrusted input into the DOM -> cross-site scripting (CWE-79)
  document.getElementById("out").innerHTML = userInput;
}

function compute(formula) {
  // Executing a caller-supplied string -> eval injection (CWE-95)
  return eval(formula);
}
