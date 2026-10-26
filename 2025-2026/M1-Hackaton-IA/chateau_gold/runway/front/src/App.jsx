import { useState } from "react";
import axios from "axios";

export default function App() {
  const [videoFile, setVideoFile] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [job, setJob] = useState(null);

  const handleVideoChange = (e) => {
    setVideoFile(e.target.files[0]);
  };

  const handleSubmit = async () => {
    if (!videoFile || !prompt) {
      alert("Veuillez sélectionner une vidéo et écrire un prompt !");
      return;
    }

    const formData = new FormData();
    formData.append("video", videoFile);

    try {
      const res = await axios.post(
        `http://127.0.0.1:8000/generate?prompt=${encodeURIComponent(prompt)}`,
        formData,
        {
          headers: { "Content-Type": "multipart/form-data" },
        }
      );
      setJob(res.data);
      alert("Job créé ! ID : " + res.data.job_id);
    } catch (err) {
      console.error(err);
      alert("Erreur lors de l'envoi du job");
    }
  };

  return (
    <div className="min-h-screen p-4 bg-gray-100 flex flex-col items-center">
      <h1 className="text-2xl font-bold mb-4">Video Prompt Studio</h1>

      <div className="bg-white p-6 rounded shadow-md w-full max-w-md">
        <label className="block mb-2 font-medium">Upload vidéo :</label>
        <input type="file" accept="video/*" onChange={handleVideoChange} />

        <label className="block mt-4 mb-2 font-medium">Prompt :</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          className="w-full border rounded p-2"
          placeholder="Ex: avion volant de gauche à droite, style cartoon"
        />

        <button
          onClick={handleSubmit}
          className="mt-4 bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600"
        >
          Envoyer au backend
        </button>
      </div>

      {job && (
        <div className="mt-6 p-4 bg-white rounded shadow-md w-full max-w-md">
          <h2 className="font-semibold">Job créé :</h2>
          <p>ID : {job.job_id}</p>
          <p>Status : {job.status}</p>
        </div>
      )}
    </div>
  );
}
