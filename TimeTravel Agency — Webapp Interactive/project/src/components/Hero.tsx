import { ChevronRight } from 'lucide-react';

export default function Hero() {
  const handleScroll = () => {
    const destinationsSection = document.getElementById('destinations');
    if (destinationsSection) {
      destinationsSection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-[#0a0a0f] via-[#1a1a2e] to-[#0a0a0f]">
        <div className="absolute inset-0 opacity-20">
          {[...Array(50)].map((_, i) => (
            <div
              key={i}
              className="absolute rounded-full bg-[#c9a84c]"
              style={{
                width: Math.random() * 3 + 1 + 'px',
                height: Math.random() * 3 + 1 + 'px',
                top: Math.random() * 100 + '%',
                left: Math.random() * 100 + '%',
                animation: `float ${Math.random() * 10 + 10}s linear infinite`,
                animationDelay: Math.random() * 5 + 's',
              }}
            />
          ))}
        </div>
      </div>

      <div className="relative z-10 text-center px-4 max-w-5xl mx-auto">
        <h1 className="animate-title text-6xl md:text-8xl font-serif text-[#c9a84c] mb-6 tracking-wide">
          TimeTravel Agency
        </h1>
        <p className="animate-title-delay text-2xl md:text-3xl text-gray-300 mb-12 font-light tracking-wider">
          Voyagez à travers le temps
        </p>
        <button
          onClick={handleScroll}
          className="group bg-[#c9a84c] text-[#0a0a0f] px-8 py-4 rounded-full font-semibold text-lg hover:bg-[#d4b55c] transition-all duration-300 hover:scale-105 shadow-lg hover:shadow-[#c9a84c]/50 flex items-center gap-2 mx-auto cursor-pointer"
        >
          Découvrir nos destinations
          <ChevronRight className="group-hover:translate-x-1 transition-transform duration-300" size={20} />
        </button>
      </div>

      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0) translateX(0); }
          25% { transform: translateY(-20px) translateX(10px); }
          50% { transform: translateY(-40px) translateX(-10px); }
          75% { transform: translateY(-20px) translateX(5px); }
        }
      `}</style>
    </section>
  );
}