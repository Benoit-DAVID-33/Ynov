import { useState } from 'react';
import { MessageCircle, X, Send } from 'lucide-react';
import { sendMessage } from '../api/mistral';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
}

interface ChatBotProps {
  onSendMessage?: (message: string) => Promise<void>;
}

export default function ChatBot({ onSendMessage }: ChatBotProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: 'Bonjour! Comment puis-je vous aider à planifier votre voyage temporel?',
      sender: 'bot',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isSending, setIsSending] = useState(false);

  const handleSend = async () => {
  if (!inputValue.trim() || isSending) return;

  const userMessage = {
    role: "user",
    content: inputValue
  };

  const updatedHistory = [...messages.map(m => ({
    role: m.sender === "user" ? "user" : "assistant",
    content: m.text
  })), userMessage];

  const userMsgDisplay = {
    id: Date.now().toString(),
    text: inputValue,
    sender: 'user',
    timestamp: new Date(),
  };

  setMessages(prev => [...prev, userMsgDisplay]);
  setInputValue("");
  setIsSending(true);

  const reply = await sendMessage(updatedHistory);

  const botMessage = {
    id: (Date.now() + 1).toString(),
    text: reply,
    sender: 'bot',
    timestamp: new Date(),
  };

  setMessages(prev => [...prev, botMessage]);
  setIsSending(false);
};

  return (
    <div className="fixed bottom-16 right-6 z-50">
      {isOpen ? (
        <div className="bg-gradient-to-br from-[#1a1a2e] to-[#0f0f1a] rounded-2xl shadow-2xl w-96 h-[500px] flex flex-col border border-[#c9a84c]/20">
          <div className="bg-[#c9a84c] text-[#0a0a0f] p-4 rounded-t-2xl flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessageCircle size={20} />
              <span className="font-semibold">Assistant Temporel</span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="hover:bg-[#d4b55c] rounded-full p-1 transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] p-3 rounded-lg ${
                    message.sender === 'user'
                      ? 'bg-[#c9a84c] text-[#0a0a0f]'
                      : 'bg-[#2a2a3e] text-gray-200'
                  }`}
                >
                  <p className="text-sm">{message.text}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 border-t border-[#c9a84c]/20">
            <div className="flex gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Votre message..."
                className="flex-1 bg-[#2a2a3e] text-gray-200 rounded-full px-4 py-2 focus:outline-none focus:ring-2 focus:ring-[#c9a84c] placeholder-gray-500"
              />
              <button
                onClick={handleSend}
                disabled={isSending}
                className="bg-[#c9a84c] text-[#0a0a0f] p-2 rounded-full hover:bg-[#d4b55c] transition-colors disabled:opacity-50"
              >
                <Send size={20} />
              </button>
            </div>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setIsOpen(true)}
          className="bg-[#c9a84c] text-[#0a0a0f] p-4 rounded-full shadow-lg hover:bg-[#d4b55c] transition-all duration-300 hover:scale-110"
        >
          <MessageCircle size={28} />
        </button>
      )}
    </div>
  );
}
