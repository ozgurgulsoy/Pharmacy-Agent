"""Main CLI interface for Pharmacy SUT Checker."""

import sys
import time
import logging
from pathlib import Path
from typing import Optional

# Add app to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich import print as rprint

from openai import OpenAI

from app.config.settings import (
    OPENAI_API_KEY,
    FAISS_INDEX_PATH,
    FAISS_METADATA_PATH,
    TOP_K_CHUNKS,
)
from app.core.parsers.input_parser import InputParser
from app.core.rag.faiss_store import FAISSVectorStore
from app.core.rag.retriever import RAGRetriever
from app.core.llm.openai_client import OpenAIClientWrapper
from app.core.llm.eligibility_checker import EligibilityChecker
from app.models.eligibility import EligibilityResult

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PharmacyCLI:
    """Pharmacy SUT Checker CLI arayüzü."""

    def __init__(self):
        self.console = Console()
        self.parser = InputParser()
        self.vector_store = None
        self.retriever = None
        self.eligibility_checker = None
        self.openai_client_wrapper = None
        self.openai_client = None

    def initialize(self):
        """Sistemi başlatır."""
        self.console.print("\n[bold cyan]Sistem başlatılıyor...[/bold cyan]")

        try:
            # OpenAI client
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
            self.openai_client_wrapper = OpenAIClientWrapper()
            self.console.print("✓ OpenAI bağlantısı kuruldu")

            # FAISS vector store
            self.vector_store = FAISSVectorStore()
            self.vector_store.load(FAISS_INDEX_PATH, FAISS_METADATA_PATH)
            stats = self.vector_store.get_stats()
            self.console.print(f"✓ FAISS index yüklendi ({stats['total_vectors']} vektör)")

            # RAG retriever
            self.retriever = RAGRetriever(self.vector_store, self.openai_client)
            self.console.print("✓ RAG retriever hazır")

            # Eligibility checker
            self.eligibility_checker = EligibilityChecker(self.openai_client_wrapper)
            self.console.print("✓ Eligibility checker hazır")

            self.console.print("\n[bold green]✓ Sistem hazır![/bold green]\n")

        except Exception as e:
            self.console.print(f"\n[bold red]✗ Hata: {e}[/bold red]")
            self.console.print("\n[yellow]Önce şunu çalıştırın:[/yellow]")
            self.console.print("  python3 scripts/setup_faiss.py\n")
            sys.exit(1)

    def show_header(self):
        """Başlık gösterir."""
        header = """
╔══════════════════════════════════════════════════════════╗
║          ECZANE SUT UYGUNLUK KONTROLÜ                   ║
║          Pharmacy SGK Eligibility Checker                ║
╚══════════════════════════════════════════════════════════╝
        """
        self.console.print(header, style="bold blue")

    def get_report_input(self) -> Optional[str]:
        """Kullanıcıdan rapor girişi alır."""
        self.console.print("\n[bold]Hasta raporunu yapıştırın ve Enter'a basın:[/bold]")
        self.console.print("[dim](Bitirmek için boş satırda Ctrl+D veya Ctrl+Z)[/dim]\n")

        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass

        report_text = '\n'.join(lines).strip()
        
        if not report_text:
            self.console.print("\n[yellow]Rapor metni boş![/yellow]")
            return None

        return report_text

    def process_report(self, report_text: str):
        """Raporu işler ve sonuçları gösterir."""
        try:
            # Start total timing
            total_start = time.time()
            timings = {}

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=self.console,
                transient=False
            ) as progress:

                # 1. Parse report
                parse_task = progress.add_task("📋 Rapor analiz ediliyor...", total=None)
                parse_start = time.time()
                parsed_report = self.parser.parse_report(report_text)
                timings['parsing'] = (time.time() - parse_start) * 1000
                progress.update(parse_task, completed=True)

                self.show_report_info(parsed_report)

                # 2. Her ilaç için RAG retrieval
                retrieval_task = progress.add_task("🔍 SUT dokümanında arama yapılıyor...", total=len(parsed_report.drugs))
                retrieval_start = time.time()
                sut_chunks_per_drug, retrieval_timings = self.retriever.retrieve_for_multiple_drugs(
                    drugs=parsed_report.drugs,
                    diagnosis=parsed_report.diagnoses[0] if parsed_report.diagnoses else None,
                    patient=parsed_report.patient,
                    top_k_per_drug=TOP_K_CHUNKS
                )
                timings['retrieval'] = (time.time() - retrieval_start) * 1000
                timings['retrieval_per_drug'] = timings['retrieval'] / len(parsed_report.drugs) if parsed_report.drugs else 0
                progress.update(retrieval_task, completed=len(parsed_report.drugs))

                # Add detailed retrieval breakdown
                if retrieval_timings:
                    timings['retrieval_breakdown'] = retrieval_timings

                # 3. Her ilaç için eligibility check
                eligibility_task = progress.add_task("💊 İlaçlar değerlendiriliyor...", total=len(parsed_report.drugs))
                eligibility_start = time.time()
                results = self.eligibility_checker.check_multiple_drugs(
                    drugs=parsed_report.drugs,
                    diagnoses=parsed_report.diagnoses,
                    patient=parsed_report.patient,
                    doctor=parsed_report.doctor,
                    sut_chunks_per_drug=sut_chunks_per_drug,
                    explanations=parsed_report.explanations
                )
                timings['eligibility_check'] = (time.time() - eligibility_start) * 1000
                timings['eligibility_per_drug'] = timings['eligibility_check'] / len(parsed_report.drugs) if parsed_report.drugs else 0
                progress.update(eligibility_task, completed=len(parsed_report.drugs))

            # Total time
            timings['total'] = (time.time() - total_start) * 1000

            # 4. Sonuçları göster
            self.show_results(results)

            # 5. Performance metrics
            self.show_performance_metrics(timings, len(parsed_report.drugs))

        except Exception as e:
            self.console.print(f"\n[bold red]✗ Hata: {e}[/bold red]")
            logger.exception("Error processing report")

    def show_report_info(self, parsed_report):
        """Rapor bilgilerini gösterir."""
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Key", style="cyan")
        info_table.add_column("Value")

        info_table.add_row("📋 Rapor No", parsed_report.report_id)
        info_table.add_row("📅 Tarih", str(parsed_report.date))
        info_table.add_row("👨‍⚕️ Doktor", f"{parsed_report.doctor.name} ({parsed_report.doctor.specialty})")
        
        if parsed_report.diagnoses:
            diagnosis = parsed_report.diagnoses[0]
            info_table.add_row("🏥 Tanı", f"{diagnosis.icd10_code} - {diagnosis.tanim}")

        info_table.add_row("💊 İlaç Sayısı", str(len(parsed_report.drugs)))

        panel = Panel(info_table, title="[bold]Rapor Bilgileri[/bold]", border_style="blue")
        self.console.print(panel)

    def show_results(self, results: list[EligibilityResult]):
        """İlaç uygunluk sonuçlarını gösterir."""
        self.console.print("\n")
        self.console.print("═" * 60, style="bold")
        self.console.print("[bold cyan]💊 İLAÇ UYGUNLUK SONUÇLARI[/bold cyan]")
        self.console.print("═" * 60, style="bold")

        for i, result in enumerate(results, 1):
            self.console.print(f"\n[bold]{i}️⃣  {result.drug_name}[/bold]")
            
            # Status
            status_emoji = {
                "ELIGIBLE": "✅",
                "NOT_ELIGIBLE": "❌",
                "CONDITIONAL": "⚠️"
            }.get(result.status, "❓")
            
            status_color = {
                "ELIGIBLE": "green",
                "NOT_ELIGIBLE": "red",
                "CONDITIONAL": "yellow"
            }.get(result.status, "white")
            
            status_text = {
                "ELIGIBLE": "SGK KAPSAMINDA KARŞILANIR",
                "NOT_ELIGIBLE": "SGK KAPSAMINDA DEĞİL",
                "CONDITIONAL": "KOŞULLU - EK BİLGİ GEREKİYOR"
            }.get(result.status, "BİLİNMİYOR")
            
            self.console.print(f"    [{status_color}]{status_emoji} {status_text}[/{status_color}]")
            
            # SUT Reference
            self.console.print(f"\n    📖 [bold]SUT Referans:[/bold] {result.sut_reference}")
            
            # Conditions
            if result.conditions:
                self.console.print(f"\n    [bold]Koşullar:[/bold]")
                for cond in result.conditions:
                    cond_emoji = "✅" if cond.is_met else ("❌" if cond.is_met == False else "❓")
                    self.console.print(f"       {cond_emoji} {cond.description}")
                    if cond.required_info and not cond.is_met:
                        self.console.print(f"          [dim]→ {cond.required_info}[/dim]")
            
            # Explanation
            if result.explanation:
                self.console.print(f"\n    [bold]Açıklama:[/bold]")
                # Wrap explanation
                for line in result.explanation.split('\n'):
                    if line.strip():
                        self.console.print(f"       {line}")
            
            # Warnings
            if result.warnings:
                self.console.print(f"\n    [bold yellow]⚠️  Uyarılar:[/bold yellow]")
                for warning in result.warnings:
                    self.console.print(f"       • {warning}", style="yellow")
            
            self.console.print("\n" + "─" * 60)

        # Summary
        eligible_count = sum(1 for r in results if r.status == "ELIGIBLE")
        conditional_count = sum(1 for r in results if r.status == "CONDITIONAL")
        not_eligible_count = sum(1 for r in results if r.status == "NOT_ELIGIBLE")

        self.console.print(f"\n[bold]Özet:[/bold]")
        self.console.print(f"  ✅ Uygun: {eligible_count}")
        self.console.print(f"  ⚠️  Koşullu: {conditional_count}")
        self.console.print(f"  ❌ Uygun değil: {not_eligible_count}")
        self.console.print()

    def show_performance_metrics(self, timings: dict, drug_count: int):
        """İşlem sürelerini gösterir."""
        self.console.print("\n")
        self.console.print("═" * 60, style="bold")
        self.console.print("[bold cyan]⚡ PERFORMANS METRİKLERİ[/bold cyan]")
        self.console.print("═" * 60, style="bold")
        
        perf_table = Table(show_header=True, header_style="bold cyan")
        perf_table.add_column("İşlem", style="cyan", width=35)
        perf_table.add_column("Süre", justify="right", style="green")
        perf_table.add_column("Detay", justify="right", style="dim")
        
        # Parsing
        perf_table.add_row(
            "📋 Rapor Analizi",
            f"{timings['parsing']:.1f}ms",
            ""
        )
        
        # RAG Retrieval - with breakdown if available
        if 'retrieval_breakdown' in timings and timings['retrieval_breakdown']:
            breakdown = timings['retrieval_breakdown']
            perf_table.add_row(
                "🔍 RAG Retrieval (Toplam)",
                f"{timings['retrieval']:.1f}ms",
                f"{timings['retrieval_per_drug']:.1f}ms/ilaç"
            )
            # Add detailed breakdown
            perf_table.add_row(
                "  ├─ Keyword Search (O(1))",
                f"{breakdown.get('keyword_search', 0):.1f}ms",
                "İlaç index lookup"
            )
            perf_table.add_row(
                "  ├─ Embedding Creation",
                f"{breakdown.get('embedding_creation', 0):.1f}ms",
                "Query vektörü"
            )
            perf_table.add_row(
                "  ├─ Vector Search",
                f"{breakdown.get('vector_search', 0):.1f}ms",
                "FAISS similarity"
            )
            perf_table.add_row(
                "  └─ Hybrid Reranking",
                f"{breakdown.get('reranking', 0):.1f}ms",
                "Score combination"
            )
        else:
            perf_table.add_row(
                "🔍 RAG Retrieval (Toplam)",
                f"{timings['retrieval']:.1f}ms",
                f"{timings['retrieval_per_drug']:.1f}ms/ilaç"
            )
        
        # Eligibility Check
        perf_table.add_row(
            "💊 Uygunluk Kontrolü (Toplam)",
            f"{timings['eligibility_check']:.1f}ms",
            f"{timings['eligibility_per_drug']:.1f}ms/ilaç"
        )
        
        # Separator
        perf_table.add_row("", "", "")
        
        # Total
        perf_table.add_row(
            "[bold]⏱️  TOPLAM İŞLEM SÜRESİ[/bold]",
            f"[bold]{timings['total']:.1f}ms[/bold]",
            f"[bold]{timings['total']/1000:.2f}s[/bold]"
        )
        
        self.console.print(perf_table)
        
        # Performance rating
        total_seconds = timings['total'] / 1000
        if total_seconds < 2:
            rating = "[bold green]🚀 Mükemmel[/bold green]"
        elif total_seconds < 5:
            rating = "[bold cyan]✨ Çok İyi[/bold cyan]"
        elif total_seconds < 10:
            rating = "[bold yellow]👍 İyi[/bold yellow]"
        else:
            rating = "[bold red]🐌 Yavaş[/bold red]"
        
        self.console.print(f"\n  Performans: {rating}")
        self.console.print(f"  İlaç sayısı: {drug_count}")
        
        # Show hybrid search efficiency
        if 'retrieval_breakdown' in timings and timings['retrieval_breakdown']:
            breakdown = timings['retrieval_breakdown']
            keyword_time = breakdown.get('keyword_search', 0)
            self.console.print(f"  Keyword lookup: {keyword_time:.2f}ms (O(1) drug index)")
        
        self.console.print()

    def run(self):
        """Ana döngü."""
        self.show_header()
        self.initialize()

        while True:
            report_text = self.get_report_input()
            
            if report_text is None:
                continue

            self.process_report(report_text)

            # Devam et?
            self.console.print("\n[bold]Başka rapor kontrol etmek ister misiniz? (e/h):[/bold] ", end="")
            try:
                choice = input().strip().lower()
                if choice != 'e':
                    break
            except (EOFError, KeyboardInterrupt):
                break

        self.console.print("\n[bold cyan]Görüşmek üzere! 👋[/bold cyan]\n")


def main():
    """CLI entry point."""
    try:
        cli = PharmacyCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\n\nÇıkılıyor...")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        logger.exception("Fatal error in CLI")
        sys.exit(1)


if __name__ == "__main__":
    main()
