export default function Dashboard() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">

      {/* Top navigation */}
      <header className="flex h-16 items-center justify-between border-b border-white/10 px-6">
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-semibold tracking-tight">
            DocLens
          </span>

          <span className="text-sm italic text-slate-500">
            by Hedobriggs
          </span>
        </div>

        <button
          type="button"
          className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/10"
        >
          Account
        </button>
      </header>

      {/* Main application */}
      <div className="flex h-[calc(100vh-4rem)]">

        {/* Document sidebar */}
        <aside className="hidden w-72 flex-col border-r border-white/10 bg-slate-950 p-4 md:flex">

          <div className="mb-5">
            <button
              type="button"
              className="w-full rounded-xl bg-blue-500 px-4 py-3 font-medium transition hover:bg-blue-400"
            >
              + Upload PDF
            </button>
          </div>

          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Documents
            </h2>

            <span className="text-xs text-slate-600">
              3 files
            </span>
          </div>

          {/* Example documents */}
          <div className="space-y-2">

            <button
              type="button"
              className="w-full rounded-xl border border-blue-500/30 bg-blue-500/10 p-3 text-left"
            >
              <p className="truncate text-sm font-medium text-slate-200">
                Employee Handbook.pdf
              </p>

              <p className="mt-1 text-xs text-slate-500">
                Ready
              </p>
            </button>

            <button
              type="button"
              className="w-full rounded-xl border border-transparent p-3 text-left transition hover:bg-white/5"
            >
              <p className="truncate text-sm font-medium text-slate-300">
                Annual Report.pdf
              </p>

              <p className="mt-1 text-xs text-slate-500">
                Ready
              </p>
            </button>

            <button
              type="button"
              className="w-full rounded-xl border border-transparent p-3 text-left transition hover:bg-white/5"
            >
              <p className="truncate text-sm font-medium text-slate-300">
                Employment Contract.pdf
              </p>

              <p className="mt-1 text-xs text-slate-500">
                Ready
              </p>
            </button>

          </div>
        </aside>

        {/* Chat workspace */}
        <section className="flex flex-1 flex-col">

          {/* Chat toolbar */}
          <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">

            <div>
              <h1 className="font-semibold">
                Document Chat
              </h1>

              <p className="mt-1 text-xs text-slate-500">
                Ask questions grounded in your documents.
              </p>
            </div>

            {/* Search scope */}
            <select
              defaultValue="documents"
              className="rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-slate-300 outline-none"
            >
              <option value="documents">
                My Documents
              </option>

              <option value="web">
                Web
              </option>

              <option value="both">
                Documents + Web
              </option>
            </select>
          </div>

          {/* Conversation area */}
          <div className="flex flex-1 items-center justify-center overflow-y-auto px-6 py-10">

            <div className="max-w-xl text-center">

              <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-500/10 text-xl text-blue-400">
                D
              </div>

              <h2 className="text-2xl font-semibold tracking-tight">
                Ask your documents
              </h2>

              <p className="mt-3 leading-7 text-slate-400">
                Upload PDFs and ask questions about their contents.
                DocLens will retrieve relevant information and provide
                answers with source references.
              </p>

              {/* Example prompts */}
              <div className="mt-8 grid gap-3 sm:grid-cols-2">

                <button
                  type="button"
                  className="rounded-xl border border-white/10 bg-white/5 p-4 text-left text-sm text-slate-300 transition hover:bg-white/10"
                >
                  Summarise this document
                </button>

                <button
                  type="button"
                  className="rounded-xl border border-white/10 bg-white/5 p-4 text-left text-sm text-slate-300 transition hover:bg-white/10"
                >
                  What are the key findings?
                </button>

                <button
                  type="button"
                  className="rounded-xl border border-white/10 bg-white/5 p-4 text-left text-sm text-slate-300 transition hover:bg-white/10"
                >
                  Compare my documents
                </button>

                <button
                  type="button"
                  className="rounded-xl border border-white/10 bg-white/5 p-4 text-left text-sm text-slate-300 transition hover:bg-white/10"
                >
                  Find relevant policies
                </button>

              </div>
            </div>
          </div>

          {/* Question input */}
          <div className="border-t border-white/10 p-4">

            <div className="mx-auto flex max-w-4xl items-end gap-3 rounded-2xl border border-white/10 bg-white/5 p-3">

              <textarea
                rows={1}
                placeholder="Ask a question about your documents..."
                className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-3 text-sm text-white outline-none placeholder:text-slate-600"
              />

              <button
                type="button"
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-500 font-semibold transition hover:bg-blue-400"
                aria-label="Send question"
              >
                ↑
              </button>

            </div>

            <p className="mt-2 text-center text-xs text-slate-600">
              Answers should be verified against the cited source documents.
            </p>
          </div>

        </section>
      </div>
    </main>
  );
}
