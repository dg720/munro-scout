import {
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
} from "@chakra-ui/react";

type Stats = {
  total: number;
  avgDistance: number;
  avgTime: number;
  avgGrade: number; // out of 5
  avgBog: number;   // out of 5
};

export default function StatsPanel({ stats }: { stats: Stats }) {
  return (
    <SimpleGrid columns={{ base: 2, md: 5 }} spacing={4} mb={10}>
      <Stat>
        <StatLabel>Total Munros</StatLabel>
        <StatNumber>{stats.total}</StatNumber>
      </Stat>

      <Stat>
        <StatLabel>Avg Distance</StatLabel>
        <StatNumber>{stats.avgDistance.toFixed(1)} km</StatNumber>
      </Stat>

      <Stat>
        <StatLabel>Avg Time</StatLabel>
        <StatNumber>{stats.avgTime.toFixed(1)} hrs</StatNumber>
      </Stat>

      <Stat>
        <StatLabel>Avg Grade</StatLabel>
        <StatNumber>
          {Math.round(stats.avgGrade)}/5
        </StatNumber>
      </Stat>

      <Stat>
        <StatLabel>Avg Bog</StatLabel>
        <StatNumber>
          {Math.round(stats.avgBog)}/5
        </StatNumber>
      </Stat>
    </SimpleGrid>
  );
}
