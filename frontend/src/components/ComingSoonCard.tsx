import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";

interface ComingSoonCardProps {
  title: string;
  description: string;
}

/** Placeholder for a page whose real content lands on a later day of the build plan. */
export function ComingSoonCard({ title, description }: ComingSoonCardProps) {
  return (
    <Card className="max-w-lg">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
    </Card>
  );
}
