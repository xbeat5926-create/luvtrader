# Merge notes

`README.md` was restored to match the initial repository content byte-for-byte so this branch should not create a README merge conflict.

The project documentation intentionally lives outside `README.md`:

- `docs/HANDOFF.md` contains setup, role, data model, email, DNS, and handoff documentation.
- `docs/VERCEL.md` contains Vercel multi-service deployment notes.

If a PR interface still shows an old README conflict, refresh the PR branch or compare against the latest commit. The final tree on this branch does not modify `README.md` relative to the initial repository content.

## Conflicted generated files

GitHub reported add/add conflicts for `frontend/src/App.jsx` and `vercel.json`. Those files were removed from this branch so the versions already present on `main` can be used during merge without a conflict.
