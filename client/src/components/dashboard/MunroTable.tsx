import {
  Box, TableContainer, Table, Thead, Tr, Th, Tbody, Td
} from "@chakra-ui/react";
import { Munro } from "../../types/munro";

export default function MunroTable({
  munros,
  onRowClick,
}: {
  munros: Munro[];
  onRowClick: (m: Munro) => void;
}) {
  return (
    <Box
      bg="white"
      border="1px solid"
      borderColor="blue.100"
      shadow="lg"
      rounded="2xl"
      overflow="hidden"
    >
      <TableContainer maxH="500px" overflowY="auto">
        <Table size="sm" variant="simple">
          <Thead position="sticky" top={0} bg="blue.500" color="white" zIndex={1}>
            <Tr>
              <Th color="white">Name</Th>
              <Th textAlign="center" color="white">Distance (km)</Th>
              <Th textAlign="center" color="white">Time (hrs)</Th>
              <Th textAlign="center" color="white">Grade</Th>
              <Th textAlign="center" color="white">Bog</Th>
            </Tr>
          </Thead>
          <Tbody>
            {munros.map((m) => (
              <Tr
                key={m.id}
                _hover={{ bg: "blue.50" }}
                cursor="pointer"
                onClick={() => onRowClick(m)}
              >
                <Td fontWeight="semibold">{m.name}</Td>
                <Td textAlign="center">{m.distance}</Td>
                <Td textAlign="center">{m.time}</Td>
                <Td textAlign="center">{m.grade}</Td>
                <Td textAlign="center">{m.bog}</Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </TableContainer>
    </Box>
  );
}
