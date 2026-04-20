import Chat from './components/Chat';

export default function Home() {
  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white flex flex-col items-center justify-center p-4">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-purple-400">
          DocMatch AI
        </h1>
        <p className="text-gray-400 mt-2">Your intelligent document assistant</p>
      </div>
      
      <Chat />
      
      <footer className="mt-12 text-gray-500 text-sm">
        Built with Next.js and FastAPI
      </footer>
    </main>
  );
}
