import Hero from './components/Hero';
import Destinations from './components/Destinations';
import DestinationQuiz from './components/DestinationQuiz';
import ChatBot from './components/ChatBot';
import Footer from './components/Footer';

function App() {
  const handleSendMessage = async (message: string) => {
    console.log('User message:', message);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <Hero />
      <Destinations />
      <DestinationQuiz />
      <Footer />
      <ChatBot onSendMessage={handleSendMessage} />
    </div>
  );
}

export default App;