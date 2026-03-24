import { X } from 'lucide-react';

const descriptions = {
  'Paris 1889': {
    title: 'Paris 1889 — La Belle Époque',
    content: `Plongez au cœur de l'une des périodes les plus fascinantes de l'histoire parisienne. 
    En 1889, Paris s'apprête à inaugurer la Tour Eiffel, chef-d'œuvre controversé de Gustave Eiffel, 
    érigée pour l'Exposition Universelle qui célèbre le centenaire de la Révolution française.
    
    Les grands boulevards bruissent d'une énergie créatrice sans précédent. Les cafés littéraires 
    accueillent Toulouse-Lautrec, Monet, Zola. Le Moulin Rouge ouvre ses portes. 
    La ville lumière porte bien son nom — le gaz laisse place à l'électricité.
    
    Votre séjour comprend : une visite exclusive du chantier de la Tour Eiffel, 
    une soirée dans un salon bourgeois, et une promenade en calèche sur les Champs-Élysées.`,
  },
  'Crétacé -65M': {
    title: 'Crétacé — 65 millions av. J.-C.',
    content: `Bienvenue sur une Terre que vous ne reconnaîtrez pas. Les continents sont différents, 
    l'atmosphère plus chaude, et les maîtres incontestés de cette planète sont les dinosaures.
    
    Vous observerez des troupeaux de Tricératops brouter dans des forêts de fougères géantes, 
    pendant que des Ptérosaures aux envergures impressionnantes planent au-dessus de mers 
    peu profondes grouillant de vie. Et si la chance vous sourit, vous apercevrez 
    de loin le roi des prédateurs : le Tyrannosaurus Rex.
    
    Votre séjour comprend : une capsule d'observation sécurisée, un guide paléontologue expert, 
    et un équipement de protection de pointe. La sécurité de nos voyageurs est notre priorité absolue.`,
  },
  'Florence 1504': {
    title: 'Florence 1504 — La Renaissance',
    content: `Florence en 1504, c'est le monde de l'art à son apogée. Michel-Ange vient tout juste 
    de terminer son David, et la ville entière vibre de cette énergie créatrice unique. 
    Léonard de Vinci peaufine ses carnets d'inventions dans son atelier.
    
    Les Médicis règnent sur une cité qui est le centre intellectuel et artistique du monde occidental. 
    Les rues pavées résonnent du marteau des sculpteurs, les palais exhibent des fresques 
    d'une beauté renversante, et les académies débattent de philosophie antique à la lueur des bougies.
    
    Votre séjour comprend : une audience privée avec des artistes de l'époque, 
    une visite des ateliers florentins, et un dîner dans un palazzo Renaissance.`,
  },
};

export default function DestinationModal({ isOpen, title, image, onClose }) {
  if (!isOpen) return null;

  const info = descriptions[title] || {
    title,
    content: 'Description non disponible.',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modale */}
      <div className="relative z-50 max-w-2xl w-full rounded-2xl overflow-hidden shadow-2xl border border-[#c9a84c]/20">

        {/* Image de fond partielle en haut */}
        <div className="relative h-56">
          <img
            src={image}
            alt={title}
            className="w-full h-full object-cover"
          />
          {/* Dégradé vers le bas */}
          <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-black/50 to-[#0a0a0f]" />

          {/* Bouton fermer */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-white hover:text-[#c9a84c] transition-colors bg-black/40 rounded-full p-1"
          >
            <X size={24} />
          </button>

          {/* Titre sur l'image */}
          <h2 className="absolute bottom-4 left-6 text-2xl font-serif text-[#c9a84c]">
            {info.title}
          </h2>
        </div>

        {/* Contenu texte */}
        <div className="bg-[#0a0a0f] px-8 py-6">
          {info.content.split('\n\n').map((paragraph, i) => (
            <p key={i} className="text-gray-300 leading-relaxed mb-4 text-sm">
              {paragraph.trim()}
            </p>
          ))}
          <button
            onClick={onClose}
            className="mt-2 border-2 border-[#c9a84c] text-[#c9a84c] px-8 py-2 rounded-full hover:bg-[#c9a84c] hover:text-[#0a0a0f] transition-all duration-300 text-sm font-semibold"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
}