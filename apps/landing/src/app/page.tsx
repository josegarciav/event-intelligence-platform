import Hero from "@/components/Hero";
import ProblemStatement from "@/components/ProblemStatement";
import PulseLine from "@/components/PulseLine";
import BentoGrid from "@/components/BentoGrid";
import ForPeople from "@/components/ForPeople";
import ForBusiness from "@/components/ForBusiness";
import Pipeline from "@/components/Pipeline";
import Metrics from "@/components/Metrics";
import Values from "@/components/Values";
import CallToAction from "@/components/CallToAction";

export default function Home() {
  return (
    <main>
      <Hero />
      <ProblemStatement />
      <PulseLine />
      <BentoGrid />
      <ForPeople />
      <PulseLine />
      <ForBusiness />
      <Pipeline />
      <Metrics />
      <Values />
      <CallToAction />
    </main>
  );
}
