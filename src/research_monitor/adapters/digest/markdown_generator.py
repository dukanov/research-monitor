"""Markdown digest generator."""

from datetime import date

from research_monitor.core import DigestEntry, DigestGenerator


class MarkdownDigestGenerator(DigestGenerator):
    """Generate markdown digest from entries."""
    
    async def generate(self, entries: list[DigestEntry], digest_date: date) -> str:
        """Generate markdown digest."""
        if not entries:
            return f"# Research Digest — {digest_date.strftime('%d.%m.%Y')}\n\nNo relevant materials found."
        
        # Group by type
        repositories = [e for e in entries if e.item.type.value == "repository"]
        papers = [e for e in entries if e.item.type.value == "paper"]
        models = [e for e in entries if e.item.type.value == "model_card"]
        
        # Sort by relevance score
        repositories.sort(key=lambda x: x.relevance_score, reverse=True)
        papers.sort(key=lambda x: x.relevance_score, reverse=True)
        models.sort(key=lambda x: x.relevance_score, reverse=True)
        
        lines = [
            f"# Research Digest — {digest_date.strftime('%d.%m.%Y')}",
            "",
            f"Items found: {len(entries)}",
            "",
        ]
        
        if papers:
            lines.extend([
                "## 📄 Papers",
                "",
            ])
            for entry in papers:
                lines.extend(self._format_entry(entry))
        
        if models:
            lines.extend([
                "## 🤖 Models",
                "",
            ])
            for entry in models:
                lines.extend(self._format_entry(entry))
        
        if repositories:
            lines.extend([
                "## 💻 Repositories",
                "",
            ])
            for entry in repositories:
                lines.extend(self._format_entry(entry))
        
        return "\n".join(lines)
    
    def _format_entry(self, entry: DigestEntry) -> list[str]:
        """Format single digest entry."""
        lines = [
            f"### [{entry.item.title}]({entry.item.url})",
            "",
            f"**Relevance:** {entry.relevance_score:.1%}",
            "",
            entry.summary,
            "",
        ]
        
        if entry.highlights:
            lines.extend([
                "**Key points:**",
                "",
            ])
            for highlight in entry.highlights:
                lines.append(f"- {highlight}")
            lines.append("")
        
        # Add metadata if available
        if entry.item.metadata:
            meta_parts = []
            for key, value in entry.item.metadata.items():
                if value:
                    meta_parts.append(f"{key}: {value}")
            
            if meta_parts:
                lines.append(f"*{' | '.join(meta_parts)}*")
                lines.append("")
        
        lines.append("---")
        lines.append("")
        
        return lines

