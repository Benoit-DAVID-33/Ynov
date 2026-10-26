import { useState } from 'react';
import DestinationCard from './DestinationCard';
import ReservationModal from './ReservationModal';
import DestinationModal from './DestinationModal';
import Toast from './Toast';

const destinations = [
  {
    image: 'https://i.imgur.com/9iEmf2d.jpg',
    title: 'Paris 1889',
    period: 'Belle Époque',
    location: 'Paris, France',
    description: "Vivez l'inauguration de la Tour Eiffel lors de l'Exposition Universelle. Découvrez le Paris des artistes, des cafés littéraires et de l'élégance parisienne à son apogée.",
    price: '12,500 €',
  },
  {
    image: 'https://i.imgur.com/p8vdmyB.jpg',
    title: 'Crétacé -65M',
    period: 'Préhistoire',
    location: 'Terre primitive',
    description: 'Explorez la période des dinosaures dans un environnement sécurisé. Observez les T-Rex, Tricératops et autres géants dans leur habitat naturel avant la grande extinction.',
    price: '45,000 €',
  },
  {
    image: 'https://i.imgur.com/6wJxMCz.jpg',
    title: 'Florence 1504',
    period: 'Renaissance',
    location: 'Florence, Italie',
    description: "Rencontrez Michel-Ange pendant la création du David. Immergez-vous dans l'effervescence artistique et intellectuelle de la Renaissance italienne.",
    price: '18,900 €',
  },
];

export default function Destinations() {
  const [modalData, setModalData] = useState(null);
  const [descData, setDescData] = useState(null);
  const [showToast, setShowToast] = useState(false);

  return (
    <section id="destinations" className="py-20 px-4 bg-[#0a0a0f]">
      <div className="max-w-7xl mx-auto">
        <h2 className="text-5xl font-serif text-[#c9a84c] text-center mb-4">
          Nos Destinations
        </h2>
        <p className="text-gray-400 text-center mb-16 text-lg">
          Voyagez à travers les époques les plus fascinantes de l'histoire
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {destinations.map((destination) => (
            <DestinationCard
              key={destination.title}
              {...destination}
              onReserveClick={(title, period) => setModalData({ title, period })}
              onDescClick={(title, image) => setDescData({ title, image })}
            />
          ))}
        </div>
      </div>

      {/* Les deux modales ICI, hors des cartes */}
      <DestinationModal
        isOpen={!!descData}
        title={descData?.title ?? ''}
        image={descData?.image ?? ''}
        onClose={() => setDescData(null)}
      />

      <ReservationModal
        isOpen={!!modalData}
        destinationName={modalData?.title ?? ''}
        period={modalData?.period ?? ''}
        onClose={() => setModalData(null)}
        onSubmit={() => {
          setModalData(null);
          setShowToast(true);
        }}
      />

      <Toast
        message="✅ Request sent! Our team will contact you within 24h."
        isVisible={showToast}
        onClose={() => setShowToast(false)}
      />
    </section>
  );
}