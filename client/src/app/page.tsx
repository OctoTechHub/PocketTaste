import { CatalogHome } from "@/components/catalog-home";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export default function Home() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />

      <main>
        {/* Real catalog from the API — hero + genre shelves + For You */}
        <CatalogHome />
      </main>

      <SiteFooter />
    </div>
  );
}
