import { Clock } from 'lucide-react';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-[#0a0a0f] border-t border-[#c9a84c]/20 py-8">
      <div className="max-w-7xl mx-auto px-4 text-center">
        <div className="flex items-center justify-center gap-2 mb-4">
          <Clock className="text-[#c9a84c]" size={24} />
          <h3 className="text-2xl font-serif text-[#c9a84c]">TimeTravel Agency</h3>
        </div>
        <p className="text-gray-400 text-sm">
          &copy; {currentYear} TimeTravel Agency. Tous droits réservés à travers le temps.
        </p>
        <p className="text-gray-500 text-xs mt-2">
          Voyagez de manière responsable. Les paradoxes temporels ne sont pas couverts par notre assurance.
        </p>
      </div>
    </footer>
  );
}
