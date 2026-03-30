import type { ApiError, HealthResponse, UploadResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

function headers(): HeadersInit {
  const h: HeadersInit = {};
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return h;
}

export async function uploadFile(
  file: File,
  onProgress?: (percent: number) => void
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return new Promise<UploadResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          const err: ApiError = JSON.parse(xhr.responseText);
          reject(new Error(err.detail));
        } catch {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      }
    });

    xhr.addEventListener("error", () =>
      reject(new Error("Network error – is the ingestion service running?"))
    );

    xhr.addEventListener("abort", () => reject(new Error("Upload cancelled")));

    xhr.open("POST", `${API_URL}/api/v1/upload/`);
    if (API_KEY) xhr.setRequestHeader("X-API-Key", API_KEY);
    xhr.send(formData);
  });
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`, { headers: headers() });
  if (!res.ok) throw new Error("Service unavailable");
  return res.json();
}
