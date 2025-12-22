function setup_3d_click() {
    // 1. Find the element
    const viewer = document.getElementById('msis_amr_3dviewer');
    
    // Safety check if element exists
    if (!viewer) {
        setTimeout(setup_3d_click, 500); // Try again in 500ms if not ready
        return;
    }

    // 2. Remove old listeners to prevent duplicates (optional cleanup)
    document.removeEventListener('click', window._3d_click_handler);

    // 3. Define the click handler
    window._3d_click_handler = function(event) {
        // Check if the click happened INSIDE the viewer
        const isClickInside = viewer.contains(event.target);

        if (isClickInside) {
            // Clicked inside -> Make it BIG
            viewer.classList.add('expanded');
        } else {
            // Clicked outside -> Make it SMALL
            viewer.classList.remove('expanded');
        }
    };

    // 4. Attach the listener to the whole page
    document.addEventListener('click', window._3d_click_handler);
}