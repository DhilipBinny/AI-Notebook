================================================================================
FUTURE ENHANCEMENTS
================================================================================

This file documents planned improvements and optimizations for future releases.

================================================================================
AI CELL IMAGE COMPRESSION (Priority: Medium)
================================================================================

Current State:
- AI Cell supports pasting/dropping images for LLM visual analysis
- Images are stored as base64 in the ipynb file within ai_data.images
- Original quality is preserved, which can make notebooks very large
- A single screenshot can be 500KB-2MB in base64

Problem:
- Large notebook files slow down save/load operations
- S3 storage costs increase
- Browser memory usage increases with many images

Proposed Solution - Client-side Compression:

1. RESIZE LARGE IMAGES
   - Max dimension: 1920px (width or height)
   - Maintain aspect ratio
   - For LLM analysis, 1920x1080 is typically sufficient

2. FORMAT-BASED COMPRESSION
   - Screenshots/photos: Convert to JPEG at 85% quality
     - A 2MB PNG screenshot becomes ~200KB JPEG with no visible quality loss
   - Diagrams with transparency: Keep as PNG but optimize
   - Already-JPEG images: Re-encode at 85% if larger than threshold

3. IMPLEMENTATION APPROACH
   - Use HTML5 Canvas API for client-side compression
   - Compress BEFORE saving to ipynb (for storage efficiency)
   - Send ORIGINAL to LLM (for best analysis quality)
   - Or: compress before both (simpler, slightly reduced LLM quality)

4. ESTIMATED IMPACT
   - 70-90% reduction in image storage size
   - Minimal visible quality loss for most use cases

5. FILES TO MODIFY
   - web/src/components/notebook/AICell.tsx (add compression utility)
   - web/src/lib/imageUtils.ts (new file for compression functions)

6. ALTERNATIVE: S3 IMAGE STORAGE
   - Store images in S3 separately with unique keys
   - Save only image references (S3 URLs) in ipynb
   - Pros: Keeps ipynb small, enables image deduplication
   - Cons: More complex, requires backend changes, orphaned images cleanup

--------------------------------------------------------------------------------
Added: 2024-12-05
Status: Planned
--------------------------------------------------------------------------------

================================================================================
