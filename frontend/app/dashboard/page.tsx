"use client";

import {
  ChangeEvent,
  FormEvent,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import ReactMarkdown from "react-markdown";


const MAX_PDF_BYTES = 50 * 1024 * 1024;
// Server-rendered controls must not invite a user-activation-only file dialog
// before React can handle the gesture. React switches snapshots on hydration.
const subscribeToClientReady = () => () => {};


type Document = {
  name: string;
  status: string;
  sizeBytes?: number;
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
  const isClientReady = useSyncExternalStore(subscribeToClientReady, () => true, () => false);

  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocument, setSelectedDocument] =
    useState<string | null>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [pendingFilename, setPendingFilename] = useState<string | null>(null);
  const [uploadNotice, setUploadNotice] = useState("");

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
    setUploadNotice("");
    if (file.size > MAX_PDF_BYTES) {
      setUploadError("PDF files must be 50 MiB or smaller.");
      event.target.value = "";
      return;
    }
    setPendingFilename(file.name);
    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(
        "/api/documents/process",
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json().catch(() => ({
        detail: `Upload failed (HTTP ${response.status}). Check the server upload limit and logs.`,
      }));

      if (!response.ok) {
        throw new Error(
          data.detail || "Document upload failed."
        );
      }

      const newDocument: Document = {
        name: data.filename,
        status: "Ready",
        sizeBytes: file.size,
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
      setUploadNotice(`${data.filename} is ready for questions.`);

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
      setPendingFilename(null);

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
        "/api/ask",
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
    <main className="doclens-dashboard flex h-full min-h-0 flex-col bg-slate-950 text-white">

      {/* ==============================================
          TOP NAVIGATION
      ============================================== */}

      <header className="flex h-16 items-center justify-between border-b border-white/10 px-6">

        <div className="flex items-baseline gap-2">

          <span className="text-xl font-semibold tracking-tight">
            DocLens
          </span>

          <span className="text-sm italic text-slate-400">
            by Hedobriggs
          </span>

        </div>


        <button
          type="button"
          onClick={async () => {
            try {
              const response = await fetch("/api/auth/logout", {
                method: "POST",
                credentials: "same-origin",
              });
              if (!response.ok) throw new Error("Logout failed");
              window.location.replace("/");
            } catch {
              alert("Unable to log out. Please try again.");
            }
          }}
          className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/10"
        >
          Log out
        </button>

      </header>


      <div className="flex min-h-0 flex-1">


        {/* ==============================================
            DOCUMENT SIDEBAR
        ============================================== */}

        <aside className="hidden w-72 flex-col overflow-y-auto border-r border-white/10 bg-slate-950 p-4 md:flex">


          {/* Hidden file input */}

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={handleFileUpload}
            className="hidden"
          />


          {/* Upload */}

          <div className="mb-4">
            <p id="upload-limits" className="mb-2 text-xs leading-5 text-slate-300">
              PDF uploads · up to {MAX_PDF_BYTES / (1024 * 1024)} MiB
            </p>

            <button
              type="button"
              onClick={openFilePicker}
              aria-describedby="upload-limits"
              disabled={!isClientReady || isUploading}
              className="w-full rounded-xl bg-blue-700 px-4 py-3 font-medium transition hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isUploading
                ? "Processing..."
                : "+ Upload PDF"}
            </button>


            <div role="status" aria-live="polite" aria-atomic="true" className="doclens-filename mt-2 text-sm text-slate-300">
              {isUploading ? (
                <>
                  <p className="break-words font-medium">{pendingFilename}</p>
                  <p className="mt-1 text-xs leading-5">Uploading and processing. Waiting for confirmation; detailed progress is not available.</p>
                  <p className="mt-1 text-xs leading-5">Cancellation is not supported by this uploader. Leaving this tab may not stop processing.</p>
                </>
              ) : uploadNotice}
            </div>
            {uploadError && (
              <p role="alert" className="mt-2 text-xs leading-5 text-red-300">
                {uploadError}
              </p>
            )}

          </div>


          {/* Documents title */}

          <div className="mb-3 flex items-center justify-between">

            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Choose a document
            </h2>

            <span className="text-xs text-slate-400">
              {documents.length}{" "}
              {documents.length === 1
                ? "file"
                : "files"}
            </span>

          </div>


          {/* Document list */}

          <p className="mb-2 text-xs leading-5 text-slate-400">Files uploaded in this tab. Select one to set the chat’s search scope.</p>
          <div className="space-y-2">

            {documents.length === 0 && (
              <p className="px-2 py-2 text-sm text-slate-400">
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
                  aria-pressed={isSelected}
                  title={document.name}

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


                  <p className="doclens-filename mt-1 text-xs text-slate-400">

                    {document.status}

                    {document.sizeBytes !== undefined &&
                      ` · ${document.sizeBytes >= 1024 * 1024 ? `${(document.sizeBytes / (1024 * 1024)).toFixed(1)} MiB` : `${Math.max(1, Math.ceil(document.sizeBytes / 1024))} KiB`}`}

                  </p>

                </button>
              );
            })}

          </div>

        </aside>


        {/* ==============================================
            CHAT WORKSPACE
        ============================================== */}

        <section className="flex min-w-0 flex-1 flex-col">


          {/* Chat toolbar */}

          <div className="flex items-center justify-between border-b border-white/10 px-5 py-3">

            <div className="min-w-0 flex-1">

              <h1 className="font-semibold">
                Document Chat
              </h1>


              <p className="doclens-filename mt-1 text-xs text-slate-400">

                {selectedDocument
                  ? `Searching ${selectedDocument}`
                  : "Ask questions grounded in your documents."}

              </p>

            </div>


            <p className="ml-4 shrink-0 text-xs text-slate-300">Search source: documents only</p>

          </div>


          {/* ==============================================
              CONVERSATION
          ============================================== */}

          <div className="flex-1 overflow-y-auto px-5 py-4">

            {messages.length === 0 ? (

              <div className="flex h-full items-center justify-center">

                <div className="max-w-xl text-center">

                  <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-500/10 text-xl text-blue-400">
                    D
                  </div>


                  <h2 className="text-2xl font-semibold tracking-tight">
                    Ask your documents
                  </h2>


                  <p className="mt-2 leading-6 text-slate-400">
                    Upload a PDF, select it, and ask a
                    question. DocLens will retrieve relevant
                    information and generate an answer from
                    the document.
                  </p>

                </div>

              </div>

            ) : (

              <div className="mx-auto max-w-4xl space-y-4">


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
                            ? "min-w-0 max-w-2xl rounded-2xl bg-blue-700 px-4 py-3 text-sm text-white"
                            : "min-w-0 max-w-2xl rounded-2xl border border-white/10 bg-white/5 px-5 py-4 text-sm text-slate-200"
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

                            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                              Sources
                            </p>


                            <div className="flex flex-wrap gap-2">

                              {uniqueCitations.map(
                                (
                                  citation,
                                  citationIndex
                                ) => (

                                  <details
                                    key={`${citation.document_name}-${citation.page_number}-${citationIndex}`}
                                    className="doclens-filename min-w-0 max-w-full rounded-lg border border-slate-500 bg-slate-900 px-3 py-2 text-xs text-slate-300"
                                  >
                                    <summary className="cursor-pointer rounded break-words leading-5">
                                      Show source reference: {" "}

                                    <span className="text-slate-300">
                                      {citation.document_name}
                                    </span>

                                    <span className="text-slate-400">
                                      {" · "}
                                    </span>

                                    <span>
                                      Page{" "}
                                      {citation.page_number}
                                    </span>
                                    </summary>
                                    <p className="mt-2 max-w-sm leading-5">Check page {citation.page_number} in your original copy of {citation.document_name}. Original-page viewing is not available in this chat.</p>
                                  </details>

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
                aria-label="Question about the selected document"
                aria-describedby="gemini-disclosure"

                value={question}

                onChange={(event) =>
                  setQuestion(
                    event.target.value
                  )
                }

                placeholder={
                  selectedDocument
                    ? "Ask about the selected document..."
                    : "Upload and select a document first..."
                }

                disabled={
                  !selectedDocument ||
                  isAsking
                }

                className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-3 text-sm text-white outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
              />


              <button
                type="submit"

                disabled={
                  !selectedDocument ||
                  !question.trim() ||
                  isAsking
                }

                className="flex h-11 shrink-0 items-center justify-center rounded-xl bg-blue-700 px-5 font-semibold text-white transition hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-40"

                aria-label="Send question"
              >
                Send
              </button>

            </form>


            {chatError && (

              <p role="alert" className="mt-2 text-center text-xs text-red-300">
                {chatError}
              </p>

            )}


            <p id="gemini-disclosure" className="mt-2 text-center text-xs leading-5 text-slate-300">
              Your questions and retrieved passages are sent to Google Gemini to generate answers. Verify answers against your original documents.
            </p>

          </div>

        </section>

      </div>

    </main>
  );
}

