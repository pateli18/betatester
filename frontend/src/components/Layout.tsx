import { NavBar } from "./Navbar";

export const Layout = ({ children }: { children: React.ReactNode }) => {
  return (
    <div>
      <NavBar />
      <div className="flex flex-col min-h-screen">
        <div className="flex-grow">
          <div className="flex-1 space-y-4 sm:p-8 sm:pt-6">{children}</div>
        </div>
      </div>
    </div>
  );
};
