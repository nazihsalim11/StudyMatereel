"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { FileVideo, Upload, Loader2, CheckCircle, XCircle, Download } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const POLL_INTERVAL_MS = 2500;

// ── Types ─────────────────────────────────────────────────────────────────────

type JobStatus = "pending" | "processing" | "completed" | "failed";

interface Job {
  job_id: string;
  filename: string;
  status: JobStatus;
  progress: number;
  video_url: string | null;
  error: string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function uploadFile(file: File): Promise<string> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${API_BASE}/upload`, { method: "POST", body });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Upload failed (${res.status})`);
  }
  const { job_id } = await res.json();
  return job_id as string;
}

async function fetchStatus(job_id: string): Promise<Job> {
  const res = await fetch(`${API_BASE}/status/${job_id}`);
  if (!res.ok) throw new Error("Status check failed");
  return res.json();
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: JobStatus }) {
  const variants: Record<JobStatus, string> = {
    pending:    "bg-yellow-900/40 text-yellow-300 border-yellow-700",
    processing: "bg-blue-900/40   text-blue-300   border-blue-700",
    completed:  "bg-emerald-900/40 text-emerald-300 border-emerald-700",
    failed:     "bg-red-900/40    text-red-300    border-red-700",
  };
  const icons: Record<JobStatus, React.ReactNode> = {
    pending:    <Loader2 size={12} className="animate-spin" />,
    processing: <Loader2 size={12} className="animate-spin" />,
    completed:  <CheckCircle size={12} />,
    failed:     <XCircle size={12} />,
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border font-medium ${variants[status]}`}>
      {icons[status]}
      {status}
    </span>
  );
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
      <div
        className="h-1.5 rounded-full bg-gradient-to-r from-violet-500 to-cyan-400 transition-all duration-700 ease-out"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

function JobCard({ job }: { job: Job }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-gray-300 truncate max-w-[60%]">{job.filename}</p>
        <StatusBadge status={job.status} />
      </div>
      {(job.status === "pending" || job.status === "processing") && (
        <ProgressBar value={job.progress} />
      )}
      {job.status === "failed" && job.error && (
        <p className="text-xs text-red-400 font-mono line-clamp-2">{job.error}</p>
      )}
    </div>
  );
}

function VideoCard({ job }: { job: Job }) {
  const videoUrl = `${API_BASE}${job.video_url}`;
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden group">
      <div className="aspect-[9/16] bg-black relative">
        <video
          src={videoUrl}
          controls
          playsInline
          className="w-full h-full object-contain"
        />
      </div>
      <div className="p-3 space-y-2">
        <p className="text-xs text-gray-400 truncate">{job.filename}</p>
        <a
          href={videoUrl}
          download
          className="flex items-center justify-center gap-2 w-full py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors"
        >
          <Download size={13} />
          Download MP4
        </a>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Home() {
  const [jobs, setJobs] = useState<Record<string, Job>>({});
  const [uploadError, setUploadError] = useState<string | null>(null);

  const startPolling = useCallback((job_id: string) => {
    const timer = setInterval(async () => {
      try {
        const data = await fetchStatus(job_id);
        setJobs((prev) => ({ ...prev, [job_id]: { ...prev[job_id], ...data } }));
        if (data.status === "completed" || data.status === "failed") {
          clearInterval(timer);
        }
      } catch {
        clearInterval(timer);
      }
    }, POLL_INTERVAL_MS);
  }, []);

  const onDrop = useCallback(
    async (accepted: File[]) => {
      setUploadError(null);
      for (const file of accepted) {
        try {
          const job_id = await uploadFile(file);
          setJobs((prev) => ({
            ...prev,
            [job_id]: {
              job_id,
              filename: file.name,
              status: "pending",
              progress: 0,
              video_url: null,
              error: null,
            },
          }));
          startPolling(job_id);
        } catch (err) {
          setUploadError(err instanceof Error ? err.message : "Upload failed");
        }
      }
    },
    [startPolling]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
    },
    multiple: true,
  });

  const allJobs = Object.values(jobs);
  const activeJobs = allJobs.filter((j) => j.status === "pending" || j.status === "processing" || j.status === "failed");
  const completedJobs = allJobs.filter((j) => j.status === "completed" && j.video_url);

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-5xl mx-auto px-6 py-12 space-y-10">

        {/* ── Header ── */}
        <header className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 bg-gray-900 border border-gray-800 rounded-full px-4 py-1.5 text-xs text-gray-400 mb-2">
            <FileVideo size={13} />
            Slides → Vertical Video
          </div>
          <h1 className="text-5xl font-black tracking-tight bg-gradient-to-r from-violet-400 via-fuchsia-400 to-cyan-400 bg-clip-text text-transparent">
            StudyReels
          </h1>
          <p className="text-gray-400 max-w-lg mx-auto">
            Upload a PDF or PowerPoint. We&apos;ll generate a narrated, captioned vertical reel — ready to share.
          </p>
        </header>

        {/* ── Drop Zone ── */}
        <div
          {...getRootProps()}
          className={`relative border-2 border-dashed rounded-3xl p-16 text-center cursor-pointer transition-all duration-200 select-none ${
            isDragActive
              ? "border-violet-400 bg-violet-950/20 scale-[1.01]"
              : "border-gray-700 hover:border-gray-600 bg-gray-900/30 hover:bg-gray-900/50"
          }`}
        >
          <input {...getInputProps()} />
          <div className="flex flex-col items-center gap-4">
            <div className={`p-5 rounded-2xl transition-colors ${isDragActive ? "bg-violet-900/50" : "bg-gray-800"}`}>
              <Upload size={32} className={isDragActive ? "text-violet-300" : "text-gray-400"} />
            </div>
            {isDragActive ? (
              <p className="text-violet-300 text-lg font-semibold">Drop to start processing…</p>
            ) : (
              <>
                <div>
                  <p className="text-gray-200 font-semibold text-lg">Drag & drop files here</p>
                  <p className="text-gray-500 text-sm mt-1">or click to browse</p>
                </div>
                <div className="flex gap-2">
                  {[".pdf", ".pptx"].map((ext) => (
                    <span key={ext} className="px-3 py-1 bg-gray-800 rounded-full text-xs text-gray-400 font-mono">
                      {ext}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {uploadError && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-950/30 border border-red-900 rounded-xl px-4 py-3">
            <XCircle size={16} />
            {uploadError}
          </div>
        )}

        {/* ── Processing Queue ── */}
        {activeJobs.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
              Processing Queue
            </h2>
            <div className="space-y-2">
              {activeJobs.map((job) => <JobCard key={job.job_id} job={job} />)}
            </div>
          </section>
        )}

        {/* ── Video Gallery ── */}
        {completedJobs.length > 0 && (
          <section className="space-y-4">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
              Video Gallery
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {completedJobs.map((job) => <VideoCard key={job.job_id} job={job} />)}
            </div>
          </section>
        )}

        {/* ── Empty state ── */}
        {allJobs.length === 0 && (
          <div className="text-center py-8 text-gray-600 text-sm">
            Your generated reels will appear here.
          </div>
        )}
      </div>
    </main>
  );
}
