import { X } from 'lucide-react';
import { useState } from 'react';

interface ReservationModalProps {
  isOpen: boolean;
  destinationName: string;
  period: string;
  onClose: () => void;
  onSubmit: () => void;
}

export default function ReservationModal({
  isOpen,
  destinationName,
  period,
  onClose,
  onSubmit,
}: ReservationModalProps) {
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    travelers: '1',
    departureDate: '',
    message: '',
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit();
    setFormData({
      fullName: '',
      email: '',
      travelers: '1',
      departureDate: '',
      message: '',
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative z-50 bg-[#1a1a2e] rounded-2xl shadow-2xl max-w-md w-full mx-4 animate-in fade-in duration-300 max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a2e] flex items-center justify-between p-6 border-b border-[#c9a84c]/20">
          <h2 className="text-2xl font-serif text-[#c9a84c]">Réserver un voyage</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-[#c9a84c] transition-colors duration-200"
          >
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div>
            <label className="block text-sm font-semibold text-[#c9a84c] mb-2">
              Destination
            </label>
            <input
              type="text"
              value={`${destinationName} — ${period}`}
              disabled
              className="w-full bg-[#0a0a0f] border border-[#c9a84c]/30 rounded-lg px-4 py-3 text-gray-300 cursor-not-allowed"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-[#c9a84c] mb-2">
              Nom complet
            </label>
            <input
              type="text"
              name="fullName"
              value={formData.fullName}
              onChange={handleChange}
              required
              className="w-full bg-[#0a0a0f] border border-[#c9a84c]/30 rounded-lg px-4 py-3 text-gray-300 focus:outline-none focus:border-[#c9a84c] transition-colors duration-200"
              placeholder="Votre nom"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-[#c9a84c] mb-2">
              Email
            </label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              className="w-full bg-[#0a0a0f] border border-[#c9a84c]/30 rounded-lg px-4 py-3 text-gray-300 focus:outline-none focus:border-[#c9a84c] transition-colors duration-200"
              placeholder="votre@email.com"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-[#c9a84c] mb-2">
              Nombre de voyageurs
            </label>
            <select
              name="travelers"
              value={formData.travelers}
              onChange={handleChange}
              className="w-full bg-[#0a0a0f] border border-[#c9a84c]/30 rounded-lg px-4 py-3 text-gray-300 focus:outline-none focus:border-[#c9a84c] transition-colors duration-200"
            >
              {[1, 2, 3, 4, 5, 6].map((num) => (
                <option key={num} value={num}>
                  {num} {num === 1 ? 'voyageur' : 'voyageurs'}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-semibold text-[#c9a84c] mb-2">
              Date de départ préférée
            </label>
            <input
              type="date"
              name="departureDate"
              value={formData.departureDate}
              onChange={handleChange}
              required
              className="w-full bg-[#0a0a0f] border border-[#c9a84c]/30 rounded-lg px-4 py-3 text-gray-300 focus:outline-none focus:border-[#c9a84c] transition-colors duration-200"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-[#c9a84c] mb-2">
              Message / Demandes spéciales (optionnel)
            </label>
            <textarea
              name="message"
              value={formData.message}
              onChange={handleChange}
              className="w-full bg-[#0a0a0f] border border-[#c9a84c]/30 rounded-lg px-4 py-3 text-gray-300 focus:outline-none focus:border-[#c9a84c] transition-colors duration-200 resize-none h-24"
              placeholder="Vos demandes spéciales..."
            />
          </div>

          <button
            type="submit"
            className="w-full bg-[#c9a84c] text-[#0a0a0f] py-3 rounded-lg font-semibold hover:bg-[#d4b55c] transition-colors duration-300 mt-6"
          >
            Confirmer ma réservation
          </button>
        </form>
      </div>
    </div>
  );
}
