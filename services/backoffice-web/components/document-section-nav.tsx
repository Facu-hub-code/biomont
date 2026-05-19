"use client";

import { useEffect, useState } from "react";

export type DocumentSectionLink = {
  id: string;
  label: string;
};

type Props = {
  sections: DocumentSectionLink[];
};

export function DocumentSectionNav({ sections }: Props) {
  const [activeId, setActiveId] = useState(sections[0]?.id ?? "");

  useEffect(() => {
    const elements = sections
      .map((section) => document.getElementById(section.id))
      .filter((el): el is HTMLElement => el != null);

    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]?.target.id) {
          setActiveId(visible[0].target.id);
        }
      },
      { rootMargin: "-30% 0px -55% 0px", threshold: [0, 0.25, 0.5, 1] },
    );

    for (const element of elements) {
      observer.observe(element);
    }

    return () => observer.disconnect();
  }, [sections]);

  return (
    <nav className="section-nav" aria-label="Secciones del documento">
      {sections.map((section) => (
        <a
          key={section.id}
          href={`#${section.id}`}
          className={
            activeId === section.id ? "section-nav-link-active" : "section-nav-link"
          }
          onClick={() => setActiveId(section.id)}
        >
          {section.label}
        </a>
      ))}
    </nav>
  );
}
