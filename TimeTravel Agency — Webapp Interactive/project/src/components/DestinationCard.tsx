import { useState } from 'react';
import { Calendar, MapPin } from 'lucide-react';

interface DestinationCardProps {
  image: string;
  title: string;
  period: string;
  description: string;
  price: string;
  location: string;
  onReserveClick: (title: string, period: string) => void;
  onDescClick: (title: string, image: string) => void;
}

export default function DestinationCard({
  image, title, period, description, price, location,
  onReserveClick, onDescClick,
}: DestinationCardProps) {
  return (
    <div className="group bg-gradient-to-br from-[#1a1a2e] to-[#0f0f1a] rounded-2xl overflow-hidden shadow-xl hover:shadow-2xl hover:shadow-[#c9a84c]/20 transition-all duration-500 hover:scale-105">
      <div className="relative h-64 overflow-hidden">
        <img src={image} alt={title} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#0a0a0f] via-transparent to-transparent opacity-60" />
        <div className="absolute top-4 right-4 bg-[#c9a84c] text-[#0a0a0f] px-4 py-2 rounded-full font-bold text-sm">
          {price}
        </div>
      </div>
      <div className="p-6">
        <h3 className="text-2xl font-serif text-[#c9a84c] mb-2">{title}</h3>
        <div className="flex items-center gap-4 mb-4 text-gray-400 text-sm">
          <div className="flex items-center gap-1">
            <Calendar size={16} />
            <span>{period}</span>
          </div>
          <div className="flex items-center gap-1">
            <MapPin size={16} />
            <span>{location}</span>
          </div>
        </div>
        <p className="text-gray-300 mb-6 leading-relaxed">{description}</p>

        <button
          onClick={() => onDescClick(title, image)}
          className="w-full bg-[#c9a84c]/10 border border-[#c9a84c]/40 text-[#c9a84c] py-3 rounded-full font-semibold hover:bg-[#c9a84c]/20 transition-all duration-300 mb-3"
        >
          En savoir plus
        </button>

        <button
          onClick={() => onReserveClick(title, period)}
          className="w-full bg-transparent border-2 border-[#c9a84c] text-[#c9a84c] py-3 rounded-full font-semibold hover:bg-[#c9a84c] hover:text-[#0a0a0f] transition-all duration-300"
        >
          Réserver
        </button>
      </div>
      {/* Plus de modale ici */}
    </div>
  );
}