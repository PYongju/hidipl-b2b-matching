const DB_NAME = "hidipl_quote_draft_files";
const STORE_NAME = "drafts";
const DB_VERSION = 1;

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB open failed"));
  });
}

export function resolveQuoteDraftStorageKey(projectData) {
  return projectData?.projectApiId ?? projectData?.projectId ?? "";
}

export async function loadQuoteDraftFiles(storageKey) {
  if (!storageKey) return [];

  try {
    const db = await openDatabase();
    const stored = await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readonly");
      const request = transaction.objectStore(STORE_NAME).get(storageKey);
      request.onsuccess = () => resolve(request.result ?? []);
      request.onerror = () => reject(request.error ?? new Error("IndexedDB read failed"));
    });
    db.close();

    if (!Array.isArray(stored)) return [];

    return stored
      .map((entry) => {
        if (!entry?.blob || !entry?.name) return null;
        return new File([entry.blob], entry.name, {
          type: entry.type || "application/octet-stream",
          lastModified: entry.lastModified ?? Date.now(),
        });
      })
      .filter(Boolean);
  } catch (error) {
    console.error("견적서 임시 파일 불러오기 실패:", error);
    return [];
  }
}

export async function saveQuoteDraftFiles(storageKey, files) {
  if (!storageKey) return;

  try {
    const payload = (files ?? []).map((file) => ({
      name: file.name,
      type: file.type || "application/octet-stream",
      lastModified: file.lastModified,
      blob: file,
    }));

    const db = await openDatabase();
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);

      if (!payload.length) {
        store.delete(storageKey);
      } else {
        store.put(payload, storageKey);
      }

      transaction.oncomplete = () => resolve();
      transaction.onerror = () =>
        reject(transaction.error ?? new Error("IndexedDB write failed"));
    });
    db.close();
  } catch (error) {
    console.error("견적서 임시 파일 저장 실패:", error);
  }
}

export async function clearQuoteDraftFiles(storageKey) {
  if (!storageKey) return;

  try {
    const db = await openDatabase();
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      transaction.objectStore(STORE_NAME).delete(storageKey);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () =>
        reject(transaction.error ?? new Error("IndexedDB delete failed"));
    });
    db.close();
  } catch (error) {
    console.error("견적서 임시 파일 삭제 실패:", error);
  }
}
