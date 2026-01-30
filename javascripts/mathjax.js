window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex"
  }
};

// Support both instant loading (document$) and regular page loads
if (typeof document$ !== 'undefined') {
  document$.subscribe(() => {
    MathJax.typesetPromise();
  });
} else {
  document.addEventListener("DOMContentLoaded", function() {
    MathJax.typesetPromise();
  });
}
