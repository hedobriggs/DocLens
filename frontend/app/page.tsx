export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="grid min-h-screen lg:grid-cols-2">

        {/* Left side — DocLens branding */}
        <section className="relative hidden overflow-hidden border-r border-white/10 lg:flex lg:flex-col lg:justify-between lg:p-12">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 via-transparent to-cyan-400/10" />

          {/* Desktop logo */}
          <div className="relative">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 font-bold">
                D
              </div>

              <div className="flex items-baseline gap-2">
                <span className="text-xl font-semibold tracking-tight">
                  DocLens
                </span>

                <span className="text-sm italic text-slate-500">
                  by Hedobriggs
                </span>
              </div>
            </div>
          </div>

          {/* Main product message */}
          <div className="relative max-w-xl">
            <p className="mb-4 text-sm font-medium uppercase tracking-[0.2em] text-blue-400">
              AI-powered document intelligence
            </p>

            <h1 className="text-5xl font-semibold leading-tight tracking-tight">
              Ask your documents.
              <br />
              <span className="text-slate-400">
                Find the source.
              </span>
            </h1>

            <p className="mt-6 max-w-lg text-lg leading-8 text-slate-400">
              Upload your documents, ask questions in natural language, and
              receive answers grounded in your own knowledge base.
            </p>
          </div>

          <p className="relative text-sm text-slate-500">
            Private documents. Grounded answers. Verifiable sources.
          </p>
        </section>

        {/* Right side — Login */}
        <section className="flex items-center justify-center px-6 py-12">
          <div className="w-full max-w-md">

            {/* Mobile logo */}
            <div className="mb-10 flex items-center gap-3 lg:hidden">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 font-bold">
                D
              </div>

              <div className="flex items-baseline gap-2">
                <span className="text-xl font-semibold tracking-tight">
                  DocLens
                </span>

                <span className="text-sm italic text-slate-500">
                  by Hedobriggs
                </span>
              </div>
            </div>

            {/* Login heading */}
            <div className="mb-8">
              <h2 className="text-3xl font-semibold tracking-tight">
                Welcome back
              </h2>

              <p className="mt-2 text-slate-400">
                Sign in to continue to your document workspace.
              </p>
            </div>

            {/* Login form */}
            <form className="space-y-5">

              {/* Email */}
              <div>
                <label
                  htmlFor="email"
                  className="mb-2 block text-sm font-medium text-slate-300"
                >
                  Email
                </label>

                <input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-slate-600 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                />
              </div>

              {/* Password */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label
                    htmlFor="password"
                    className="text-sm font-medium text-slate-300"
                  >
                    Password
                  </label>

                  <button
                    type="button"
                    className="text-sm text-blue-400 transition hover:text-blue-300"
                  >
                    Forgot password?
                  </button>
                </div>

                <input
                  id="password"
                  type="password"
                  placeholder="Enter your password"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-slate-600 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                />
              </div>

              {/* Sign in */}
              <button
                type="submit"
                className="w-full rounded-xl bg-blue-500 px-4 py-3 font-medium text-white transition hover:bg-blue-400"
              >
                Sign in
              </button>
            </form>

            {/* Divider */}
            <div className="my-7 flex items-center gap-4">
              <div className="h-px flex-1 bg-white/10" />

              <span className="text-xs uppercase tracking-wider text-slate-600">
                or
              </span>

              <div className="h-px flex-1 bg-white/10" />
            </div>

            {/* Google login */}
            <button
              type="button"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 font-medium text-slate-200 transition hover:bg-white/10"
            >
              Continue with Google
            </button>

            {/* Create account */}
            <p className="mt-8 text-center text-sm text-slate-400">
              Don&apos;t have an account?{" "}
              <button
                type="button"
                className="font-medium text-blue-400 transition hover:text-blue-300"
              >
                Create account
              </button>
            </p>

          </div>
        </section>
      </div>
    </main>
  );
}
