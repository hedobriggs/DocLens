                        {uniqueCitations.length > 0 && (

                          <div className="mt-5 border-t border-white/10 pt-4">

                            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                              Sources
                            </p>


                            <div className="flex flex-wrap gap-2">

                              {uniqueCitations.map(
                                (
                                  citation,
                                  citationIndex
                                ) => (

                                  <div
                                    key={`${citation.document_name}-${citation.page_number}-${citationIndex}`}

                                    className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-400"
                                  >

                                    <span className="text-slate-300">
                                      {citation.document_name}
                                    </span>

                                    <span className="text-slate-600">
                                      {" · "}
                                    </span>

                                    <span>
                                      Page{" "}
                                      {citation.page_number}
                                    </span>

                                  </div>

                                )
                              )}

                            </div>

                          </div>

                        )}

                      </div>

                    </div>

                  );
                })}


                {/* ==============================================
                    LOADING
                ============================================== */}

                {isAsking && (

                  <div className="flex justify-start">

                    <div className="rounded-2xl border border-white/10 bg-white/5 px-5 py-4 text-sm text-slate-400">

                      Searching documents and generating
                      answer...

                    </div>

                  </div>

                )}

              </div>

            )}

          </div>


          {/* ==============================================
              QUESTION INPUT
          ============================================== */}

          <div className="border-t border-white/10 p-4">

            <form
              onSubmit={handleAsk}

              className="mx-auto flex max-w-4xl items-end gap-3 rounded-2xl border border-white/10 bg-white/5 p-3"
            >


              <textarea
                rows={1}

                value={question}

                onChange={(event) =>
                  setQuestion(
                    event.target.value
                  )
                }

                placeholder={
                  selectedDocument
                    ? `Ask about ${selectedDocument}...`
                    : "Upload and select a document first..."
                }

                disabled={
                  !selectedDocument ||
                  isAsking
                }

                className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-3 text-sm text-white outline-none placeholder:text-slate-600 disabled:cursor-not-allowed"
              />


              <button
                type="submit"

                disabled={
                  !selectedDocument ||
                  !question.trim() ||
                  isAsking
                }

                className="flex h-11 shrink-0 items-center justify-center rounded-xl bg-blue-500 px-5 font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-40"

                aria-label="Send question"
              >
                Send
              </button>

            </form>


            {chatError && (

              <p className="mt-2 text-center text-xs text-red-400">
                {chatError}
              </p>

            )}


            <p className="mt-2 text-center text-xs text-slate-600">
              Answers should be verified against the cited
              source documents.
            </p>

          </div>

        </section>

      </div>

    </main>
