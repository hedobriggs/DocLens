"use client";

import {
  ChangeEvent,
  FormEvent,
  useRef,
  useState,
} from "react";

import ReactMarkdown from "react-markdown";


type Document = {
  name: string;
  status: string;
  chunks?: number;
};


type Citation = {
  document_name: string;
  page_number: number;
  chunk_id: string;
};


type Message = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
};


export default function Dashboard() {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocument, setSelectedDocument] =
    useState<string | null>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAsking, setIsAsking] = useState(false);
  const [chatError, setChatError] = useState("");


  // --------------------------------------------------
  // Open file picker
  // --------------------------------------------------

  function openFilePicker() {
    fileInputRef.current?.click();
  }


  // --------------------------------------------------
  // Deduplicate citations
  // --------------------------------------------------

  function getUniqueCitations(
    citations: Citation[] = []
  ) {
    const seen = new Set<string>();

    return citations.filter((citation) => {
      const key =
        `${citation.document_name}-${citation.page_number}`;

      if (seen.has(key)) {
        return false;
      }

      seen.add(key);
      return true;
    });
  }


  // --------------------------------------------------
  // Upload + process document
  // --------------------------------------------------

  async function handleFileUpload(
    event: ChangeEvent<HTMLInputElement>
  ) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setUploadError("");
    setIsUploading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/documents/process",
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Document upload failed."
        );
      }

      const newDocument: Document = {
        name: data.filename,
        status: "Ready",
        chunks: data.total_chunks,
      };

      // Replace the existing sidebar entry if the
      // same filename is uploaded again.
      setDocuments((currentDocuments) => {
        const withoutExisting =
          currentDocuments.filter(
            (document) =>
              document.name !== data.filename
          );

        return [
          ...withoutExisting,
          newDocument,
        ];
      });

      setSelectedDocument(data.filename);

    } catch (error) {
      if (error instanceof Error) {
        setUploadError(error.message);
      } else {
        setUploadError(
          "Document upload failed."
        );
      }

    } finally {
      setIsUploading(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }


  // --------------------------------------------------
  // Ask question
  // --------------------------------------------------

  async function handleAsk(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    const cleanQuestion = question.trim();

    if (!cleanQuestion || isAsking) {
      return;
    }

    setChatError("");
    setQuestion("");

    const userMessage: Message = {
      role: "user",
      content: cleanQuestion,
    };

    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
    ]);

    setIsAsking(true);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/ask",
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            question: cleanQuestion,
            document_name: selectedDocument,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Could not answer the question."
        );
      }

      const assistantMessage: Message = {
        role: "assistant",
        content: data.answer,
        citations: data.citations,
      };

      setMessages((currentMessages) => [
        ...currentMessages,
        assistantMessage,
      ]);

    } catch (error) {
      if (error instanceof Error) {
        setChatError(error.message);
      } else {
        setChatError(
          "Could not answer the question."
        );
      }

    } finally {
      setIsAsking(false);
    }
  }


  // --------------------------------------------------
  // UI
  // --------------------------------------------------

  return (
    <main className="min-h-screen bg-slate-950 text-white">

      {/* ==============================================
          TOP NAVIGATION
      ============================================== */}

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


      <div className="flex h-[calc(100vh-4rem)]">


        {/* ==============================================
            DOCUMENT SIDEBAR
        ============================================== */}

        <aside className="hidden w-72 flex-col border-r border-white/10 bg-slate-950 p-4 md:flex">


          {/* Hidden file input */}

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={handleFileUpload}
            className="hidden"
          />


          {/* Upload */}

          <div className="mb-5">

            <button
              type="button"
              onClick={openFilePicker}
              disabled={isUploading}
              className="w-full rounded-xl bg-blue-500 px-4 py-3 font-medium transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isUploading
                ? "Processing..."
                : "+ Upload PDF"}
            </button>


            {uploadError && (
              <p className="mt-2 text-xs text-red-400">
                {uploadError}
              </p>
            )}

          </div>


          {/* Documents title */}

          <div className="mb-3 flex items-center justify-between">

            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Documents
            </h2>

            <span className="text-xs text-slate-600">
              {documents.length}{" "}
              {documents.length === 1
                ? "file"
                : "files"}
            </span>

          </div>


          {/* Document list */}

          <div className="space-y-2">

            {documents.length === 0 && (
              <p className="px-3 py-4 text-sm text-slate-600">
                No documents uploaded yet.
              </p>
            )}


            {documents.map((document) => {

              const isSelected =
                selectedDocument === document.name;

              return (
                <button
                  key={document.name}
                  type="button"

                  onClick={() =>
                    setSelectedDocument(
                      document.name
                    )
                  }

                  className={
                    isSelected
                      ? "w-full rounded-xl border border-blue-500/30 bg-blue-500/10 p-3 text-left"
                      : "w-full rounded-xl border border-transparent p-3 text-left transition hover:bg-white/5"
                  }
                >

                  <p className="truncate text-sm font-medium text-slate-300">
                    {document.name}
                  </p>


                  <p className="mt-1 text-xs text-slate-500">

                    {document.status}

                    {document.chunks !== undefined &&
                      ` · ${document.chunks} chunks`}

                  </p>

                </button>
              );
            })}

          </div>

        </aside>


        {/* ==============================================
            CHAT WORKSPACE
        ============================================== */}

        <section className="flex flex-1 flex-col">


          {/* Chat toolbar */}

          <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">

            <div>

              <h1 className="font-semibold">
                Document Chat
              </h1>


              <p className="mt-1 text-xs text-slate-500">

                {selectedDocument
                  ? `Searching ${selectedDocument}`
                  : "Ask questions grounded in your documents."}

              </p>

            </div>


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


          {/* ==============================================
              CONVERSATION
          ============================================== */}

          <div className="flex-1 overflow-y-auto px-6 py-8">

            {messages.length === 0 ? (

              <div className="flex h-full items-center justify-center">

                <div className="max-w-xl text-center">

                  <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-500/10 text-xl text-blue-400">
                    D
                  </div>


                  <h2 className="text-2xl font-semibold tracking-tight">
                    Ask your documents
                  </h2>


                  <p className="mt-3 leading-7 text-slate-400">
                    Upload a PDF, select it, and ask a
                    question. DocLens will retrieve relevant
                    information and generate an answer from
                    the document.
                  </p>

                </div>

              </div>

            ) : (

              <div className="mx-auto max-w-4xl space-y-6">


                {messages.map((message, index) => {

                  const uniqueCitations =
                    getUniqueCitations(
                      message.citations
                    );

                  return (

                    <div
                      key={index}

                      className={
                        message.role === "user"
                          ? "flex justify-end"
                          : "flex justify-start"
                      }
                    >

                      <div
                        className={
                          message.role === "user"
                            ? "max-w-2xl rounded-2xl bg-blue-500 px-4 py-3 text-sm text-white"
                            : "max-w-2xl rounded-2xl border border-white/10 bg-white/5 px-5 py-4 text-sm text-slate-200"
                        }
                      >


                        {/* ==================================
                            MESSAGE CONTENT
                        ================================== */}

                        {message.role === "assistant" ? (

                          <div className="space-y-3">

                            <ReactMarkdown
                              components={{

                                p: ({ children }) => (
                                  <p className="mb-3 leading-7 text-slate-200 last:mb-0">
                                    {children}
                                  </p>
                                ),


                                strong: ({ children }) => (
                                  <strong className="font-semibold text-white">
                                    {children}
                                  </strong>
                                ),


                                h1: ({ children }) => (
                                  <h1 className="mb-3 mt-5 text-lg font-semibold text-white first:mt-0">
                                    {children}
                                  </h1>
                                ),


                                h2: ({ children }) => (
                                  <h2 className="mb-2 mt-5 text-base font-semibold text-white first:mt-0">
                                    {children}
                                  </h2>
                                ),


                                h3: ({ children }) => (
                                  <h3 className="mb-2 mt-4 font-semibold text-white first:mt-0">
                                    {children}
                                  </h3>
                                ),


                                ul: ({ children }) => (
                                  <ul className="mb-4 ml-5 list-disc space-y-2 text-slate-200">
                                    {children}
                                  </ul>
                                ),


                                ol: ({ children }) => (
                                  <ol className="mb-4 ml-5 list-decimal space-y-2 text-slate-200">
                                    {children}
                                  </ol>
                                ),


                                li: ({ children }) => (
                                  <li className="pl-1 leading-6">
                                    {children}
                                  </li>
                                ),


                                code: ({ children }) => (
                                  <code className="rounded bg-black/30 px-1.5 py-0.5 text-xs text-blue-300">
                                    {children}
                                  </code>
                                ),

                              }}
                            >
                              {message.content}
                            </ReactMarkdown>

                          </div>

                        ) : (

                          <p className="leading-6">
                            {message.content}
                          </p>

                        )}


                        {/* ==================================
                            SOURCES
                        ================================== */}

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

                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-500 font-semibold transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-40"

                aria-label="Send question"
              >
                ↑
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
  );
}
