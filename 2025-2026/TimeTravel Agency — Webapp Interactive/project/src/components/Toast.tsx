import { useEffect } from 'react';

interface ToastProps {
  message: string;
  isVisible: boolean;
  onClose: () => void;
}

export default function Toast({ message, isVisible, onClose }: ToastProps) {
  useEffect(() => {
    if (isVisible) {
      const timer = setTimeout(onClose, 4000);
      return () => clearTimeout(timer);
    }
  }, [isVisible, onClose]);

  if (!isVisible) return null;

  return (
    <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-40 animate-in slide-in-from-bottom-4 duration-300">
      <div className="bg-[#1a1a2e] border border-[#c9a84c]/50 text-gray-200 px-6 py-4 rounded-lg shadow-lg flex items-center gap-3 whitespace-nowrap">
        <span className="text-green-400">✅</span>
        <span>{message}</span>
      </div>
    </div>
  );
}
