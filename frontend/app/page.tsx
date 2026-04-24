import ChatInterface from "./components/ChatInterface";

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-100 py-8 px-4 sm:px-6 lg:px-8">
      <main>
        <div className="max-w-4xl mx-auto mb-6 text-center">
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight sm:text-4xl">
            Multi-Agent Medical Assistant
          </h1>
          <p className="mt-2 text-lg text-slate-600">
            Intelligent medical triage and symptom analysis powered by LangGraph.
          </p>
        </div>
        <ChatInterface />
      </main>
    </div>
  );
}
