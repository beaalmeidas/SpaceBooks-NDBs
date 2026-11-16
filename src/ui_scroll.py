"""Rolagem animada no contêiner principal do Streamlit após a navegação."""
import json
import streamlit as st
import streamlit.components.v1 as components


def render_pending_scroll():
    target = st.session_state.pop('_scroll_target', None)
    if not target:
        return
    components.html('''<script>
const doc = window.parent.document;
const targetId = ''' + json.dumps(target) + ''';
let observer;
function scrollToSection() {
    const target = doc.getElementById(targetId);
    const main = doc.querySelector('[data-testid="stMain"]');
    if (!target || !main) return false;
    if (observer) observer.disconnect();
    // Let Streamlit finish laying out this render before measuring the section.
    requestAnimationFrame(() => requestAnimationFrame(() => {
        const start = main.scrollTop;
        const end = Math.max(0, Math.min(main.scrollHeight - main.clientHeight,
            start + target.getBoundingClientRect().top - main.getBoundingClientRect().top - 28));
        const duration = window.parent.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 1100;
        const oldBehavior = main.style.scrollBehavior;
        main.style.scrollBehavior = 'auto';
        let began;
        let cancelled = false;
        const stop = () => { cancelled = true; cleanup(); };
        function cleanup() {
            main.style.scrollBehavior = oldBehavior;
            main.removeEventListener('wheel', stop);
            main.removeEventListener('touchstart', stop);
        }
        main.addEventListener('wheel', stop, {passive:true});
        main.addEventListener('touchstart', stop, {passive:true});
        function frame(now) {
            if (cancelled) return;
            if (began === undefined) began = now;
            const t = duration ? Math.min(1, (now - began) / duration) : 1;
            const eased = t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3)/2;
            main.scrollTop = start + (end-start)*eased;
            if (t < 1) requestAnimationFrame(frame); else cleanup();
        }
        requestAnimationFrame(frame);
    }));
    return true;
}
if (!scrollToSection()) {
    observer = new MutationObserver(scrollToSection);
    observer.observe(doc.body, {childList:true, subtree:true});
    setTimeout(() => observer.disconnect(), 5000);
}
</script>''', height=0)
