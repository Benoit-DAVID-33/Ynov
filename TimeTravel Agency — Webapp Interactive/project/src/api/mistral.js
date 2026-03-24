const MISTRAL_API_KEY = import.meta.env.VITE_MISTRAL_API_KEY;

const SYSTEM_PROMPT = `Tu es l'assistant virtuel de TimeTravel Agency, 
une agence de voyage temporel de luxe.
Tu conseilles les clients sur 3 destinations :
- Paris 1889 : Belle Époque, Tour Eiffel, Exposition Universelle. Prix : 4 500€
- Crétacé -65M : dinosaures, nature préhistorique sauvage. Prix : 8 900€  
- Florence 1504 : Renaissance, Michel-Ange, Léonard de Vinci. Prix : 5 200€
Ton ton : professionnel, chaleureux, passionné d'histoire.
Réponds toujours en français. Sois concis (3-4 phrases max).`;

export async function sendMessage(messages) {
  const response = await fetch("https://api.mistral.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${MISTRAL_API_KEY}`
    },
    body: JSON.stringify({
      model: "mistral-small-latest",
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        ...messages
      ],
      max_tokens: 300
    })
  });
  const data = await response.json();
  return data.choices[0].message.content;
}