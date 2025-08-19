import {
  ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip
} from "recharts";
import { Box, Text } from "@chakra-ui/react";
import { Munro } from "../../types/munro";

function CustomTooltip({ active, payload }: any) {
  if (active && payload && payload.length) {
    return (
      <Box bg="white" border="1px solid #ccc" px={3} py={2} rounded="md" shadow="sm">
        <Text fontWeight="semibold">{payload[0].payload.name}</Text>
      </Box>
    );
  }
  return null;
}

export default function ScatterPlot({ data }: { data: Munro[] }) {
  return (
    <Box h="300px" mb={10}>
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 10, right: 30, bottom: 10, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="distance"
            name="Distance (km)"
            domain={[5, 40]}
            label={{ value: "Distance (km)", position: "insideBottomRight", offset: -5 }}
          />
          <YAxis
            type="number"
            dataKey="time"
            name="Time (hrs)"
            label={{ value: "Time (hrs)", angle: -90, position: "insideLeft" }}
          />
          <ChartTooltip content={<CustomTooltip />} cursor={{ strokeDasharray: "3 3" }} />
          <Scatter name="Munros" data={data} fill="#3182ce" isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </Box>
  );
}
